"""Review session: engine orchestration behind the review UI.

Pure engine code — no web-framework imports — so the session is fully
testable without the ``ui`` extra installed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from privacy_firewall.detectors import (
    AadhaarDetector,
    AccountDetector,
    DetectorRegistry,
    EmailDetector,
    IFSCDetector,
    PANDetector,
    PhoneDetector,
    UpiDetector,
)
from privacy_firewall.engine.context import ContextScorer
from privacy_firewall.engine.decision import (
    DecisionEngine,
    ReviewDecision,
    ReviewEntry,
    ReviewPlan,
    SuggestedAction,
    file_sha256,
)
from privacy_firewall.engine.fusion import FusionEngine
from privacy_firewall.engine.ocr_pipeline import get_merged_document, get_pipeline_summary
from privacy_firewall.engine.redaction import RedactionPlanner, RedactionType
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import BoundingBox, Span
from privacy_firewall.policy.models import Policy
from privacy_firewall.renderer.page_images import (
    DEFAULT_DPI,
    render_page_image,
    render_page_image_bytes,
)
from privacy_firewall.renderer.pdf_renderer import PDFRenderer


class ReviewSession:
    """One review of one PDF: pipeline results plus mutable decisions."""

    def __init__(
        self,
        pdf_path: Path,
        policy: Policy,
        *,
        force_ocr: bool = False,
        auto: bool = False,
        ocr_provider: str | None = None,
        dpi: int = DEFAULT_DPI,
        lazy: bool = False,
    ) -> None:
        """Set up the session and (unless *lazy*) run the pipeline.

        Args:
            pdf_path: The PDF under review.
            policy: Policy providing the suggested actions.
            force_ocr: Force the OCR pipeline.
            auto: Let diagnostics choose the pipeline.
            ocr_provider: Specific OCR engine name.
            dpi: Page-image render resolution.
            lazy: Skip the pipeline; the caller invokes :meth:`run` later
                (e.g. in a background thread while the server starts).
        """
        self.pdf_path = Path(pdf_path)
        self.policy = policy
        self.dpi = dpi
        self.force_ocr = force_ocr
        self.auto = auto
        self.ocr_provider = ocr_provider
        self._page_cache: dict[int, bytes] = {}
        self._preview_pdf: bytes | None = None
        self._preview_key: int | None = None
        self._document: Document | None = None
        self._plan: ReviewPlan | None = None
        self.source = ""
        self.status = "starting"
        self.error: str | None = None
        self.restored_decisions = 0
        self.restored_manual = 0

        if not lazy:
            self.run()

    @property
    def document(self) -> Document:
        """The parsed document (raises until the pipeline has finished)."""
        if self._document is None:
            msg = "review pipeline has not finished"
            raise RuntimeError(msg)
        return self._document

    @property
    def plan(self) -> ReviewPlan:
        """The review plan (raises until the pipeline has finished)."""
        if self._plan is None:
            msg = "review pipeline has not finished"
            raise RuntimeError(msg)
        return self._plan

    @property
    def is_ready(self) -> bool:
        """Whether the pipeline finished and the plan is available."""
        return self.status == "ready"

    def status_payload(self) -> dict[str, Any]:
        """JSON-friendly pipeline status for the UI loading screen."""
        return {"status": self.status, "detail": self.error or ""}

    def run(self) -> None:
        """Execute the detection pipeline (blocking).

        Updates :attr:`status` as stages advance; on failure the status
        becomes ``"error"`` with the message in :attr:`error`, and the
        exception is re-raised for eager (constructor) callers.
        """
        try:
            self._run_pipeline(force_ocr=self.force_ocr, auto=self.auto)
        except Exception as exc:
            self.status = "error"
            self.error = str(exc)
            raise

    def rerun(self, *, force_ocr: bool = True, ocr_provider: str | None = None) -> None:
        """Re-run the pipeline (typically forcing OCR), discarding decisions.

        Callers must ensure no other pipeline run is in flight (the
        server serialises reruns behind a lock).

        Args:
            force_ocr: Force the OCR pipeline on this run.
            ocr_provider: Specific OCR engine name.
        """
        self.error = None
        self.ocr_provider = ocr_provider or self.ocr_provider
        self._preview_pdf = None
        self._preview_key = None
        try:
            self._run_pipeline(force_ocr=force_ocr, auto=False, restore=False)
        except Exception as exc:
            self.status = "error"
            self.error = str(exc)
            raise

    def _run_pipeline(self, *, force_ocr: bool, auto: bool, restore: bool = True) -> None:
        """Parse, detect, decide — then optionally restore saved decisions."""
        self.status = "parsing"
        document, self.source = get_merged_document(
            self.pdf_path,
            force_ocr=force_ocr,
            auto=auto,
            ocr_provider=self.ocr_provider,
            progress=self._set_stage,
        )

        self.status = "detecting"
        registry = DetectorRegistry()
        for detector in (
            PANDetector(),
            AadhaarDetector(),
            EmailDetector(),
            PhoneDetector(),
            UpiDetector(),
            IFSCDetector(),
            AccountDetector(),
        ):
            registry.register(detector)

        detections = registry.run_all(document, values_only=True).detections
        detections = ContextScorer().apply(document, detections)
        detections = FusionEngine().fuse(detections).detections

        plan = DecisionEngine().decide(
            detections,
            self.policy,
            source_path=str(self.pdf_path),
            source_sha256=file_sha256(self.pdf_path),
        )
        self.restored_decisions = 0
        self.restored_manual = 0
        if restore:
            self._restore_saved_plan(plan)

        self._document = document
        self._plan = plan
        self.status = "ready"

    def _set_stage(self, stage: str) -> None:
        """Progress callback for :func:`get_merged_document`."""
        self.status = stage

    def _restore_saved_plan(self, plan: ReviewPlan) -> None:
        """Merge a previously saved review plan into a fresh one.

        Restores user decisions (matched by detection id) and manual
        marks from ``<name>.review.json`` when the file exists and its
        recorded document hash matches — so closing and reopening a
        review resumes where it left off.
        """
        path = self.plan_file_path
        if not path.exists():
            return
        try:
            saved = ReviewPlan.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return  # unreadable/corrupt plan — start fresh
        if saved.source_sha256 != plan.source_sha256:
            return

        for saved_entry in saved.entries:
            if saved_entry.detection.detector_name == "manual":
                if plan.entry_by_id(saved_entry.detection_id) is None:
                    plan.entries.append(saved_entry)
                    self.restored_manual += 1
            elif saved_entry.decision is not None:
                entry = plan.entry_by_id(saved_entry.detection_id)
                if entry is not None and entry.decision is None:
                    entry.decision = saved_entry.decision
                    self.restored_decisions += 1

        if self.restored_manual:
            plan.entries.sort(
                key=lambda e: (
                    e.detection.page_number,
                    e.detection.span.start,
                    e.detection.detection_type,
                )
            )

    @property
    def plan_file_path(self) -> Path:
        """Where the review plan is persisted (next to the source PDF)."""
        return self.pdf_path.with_suffix(".review.json")

    def summary(self) -> dict[str, Any]:
        """Everything the UI needs to render, as JSON-friendly data."""
        return {
            "source": str(self.pdf_path),
            "policy": self.policy.name,
            "pipeline": get_pipeline_summary(self.source),
            "counts": self.plan.counts(),
            "restored": {
                "decisions": self.restored_decisions,
                "manual": self.restored_manual,
            },
            "pages": [
                {"page_number": p.page_number, "width": p.width, "height": p.height}
                for p in self.document.pages
            ],
            "entries": [self.entry_dict(e) for e in self.plan.entries],
        }

    @staticmethod
    def entry_dict(entry: ReviewEntry) -> dict[str, Any]:
        """JSON-friendly representation of one review entry."""
        return {
            "detection_id": entry.detection_id,
            "type": entry.detection.detection_type,
            "detector": entry.detection.detector_name,
            "text": entry.detection.text,
            "page_number": entry.detection.page_number,
            "confidence": entry.detection.confidence,
            "bbox": entry.detection.bbox.model_dump(),
            "reasons": list(entry.detection.reasons) + list(entry.suggestion_reasons),
            "suggested_action": entry.suggested_action.value,
            "decision": entry.decision.value if entry.decision else None,
            "effective_action": entry.effective_action.value,
        }

    def set_decision(self, detection_id: str, decision: str | None) -> bool:
        """Record a user decision (``"redact"``, ``"keep"``, or ``None``).

        Args:
            detection_id: Stable id of the detection.
            decision: The decision value, or ``None`` to clear it.

        Returns:
            ``True`` if the entry was found and updated.
        """
        entry = self.plan.entry_by_id(detection_id)
        if entry is None:
            return False
        entry.decision = ReviewDecision(decision) if decision else None
        return True

    def page_words(self, page_number: int) -> list[dict[str, Any]]:
        """Word-level text geometry for one page (drives the UI text layer).

        Args:
            page_number: The 1-based page number.

        Returns:
            One dict per word: ``{"text", "x0", "y0", "x1", "y1"}`` in
            PDF coordinates.

        Raises:
            ValueError: If the page does not exist.
        """
        for page in self.document.pages:
            if page.page_number != page_number:
                continue
            return [
                {"text": span.text, **span.bbox.model_dump()}
                for block in page.blocks
                if isinstance(block, TextBlock)
                for span in block.spans
            ]
        msg = f"page {page_number} not found"
        raise ValueError(msg)

    def mark_text(
        self, text: str, label: str, *, case_sensitive: bool = False
    ) -> list[ReviewEntry]:
        """Mark every instance of *text* in the document as PII.

        Each occurrence becomes a manual ``Detection`` (detector name
        ``"manual"``, confidence 1.0) with the given label as its
        detection type and an explicit *redact* decision — the reviewer
        can still flip individual instances to *keep* afterwards.

        Whitespace in *text* is treated flexibly (any run of whitespace
        matches any other), so selections spanning line wraps still match.

        Args:
            text: The text to search for (as selected by the reviewer).
            label: Detection-type label for the new entries (e.g. ``NAME``).
            case_sensitive: Require an exact-case match.

        Returns:
            The newly added entries (empty if nothing matched or every
            match was already in the plan).

        Raises:
            ValueError: If *text* or *label* is blank.
        """
        tokens = text.split()
        if not tokens:
            msg = "text to mark must not be blank"
            raise ValueError(msg)
        normalized_label = "_".join(label.split()).upper()
        if not normalized_label:
            msg = "label must not be blank"
            raise ValueError(msg)

        pattern = re.compile(
            r"\s+".join(re.escape(token) for token in tokens),
            0 if case_sensitive else re.IGNORECASE,
        )
        known_ids = {entry.detection_id for entry in self.plan.entries}
        added: list[ReviewEntry] = []

        for page in self.document.pages:
            # Spans are offset into a page-level concatenation of block
            # texts so the same text at the same block-relative offset in
            # two blocks still yields distinct detection ids.
            page_offset = 0
            for block in page.blocks:
                if not isinstance(block, TextBlock):
                    continue
                base = page_offset
                page_offset += len(block.text) + 1
                for match in pattern.finditer(block.text):
                    detection = Detection(
                        detector_name="manual",
                        detection_type=normalized_label,
                        text=match.group(),
                        span=Span(start=base + match.start(), end=base + match.end()),
                        bbox=self._char_range_bbox(block, match.start(), match.end()),
                        page_number=page.page_number,
                        confidence=1.0,
                        reasons=("marked as PII by the reviewer",),
                    )
                    if detection.detection_id in known_ids:
                        continue
                    known_ids.add(detection.detection_id)
                    entry = ReviewEntry(
                        detection=detection,
                        suggested_action=SuggestedAction.REDACT,
                        suggestion_reasons=("manually marked during review",),
                        decision=ReviewDecision.REDACT,
                    )
                    self.plan.entries.append(entry)
                    added.append(entry)

        if added:
            self.plan.entries.sort(
                key=lambda e: (
                    e.detection.page_number,
                    e.detection.span.start,
                    e.detection.detection_type,
                )
            )
        return added

    def remove_manual_entry(self, detection_id: str) -> bool:
        """Remove a manually marked entry from the plan.

        Only entries created by :meth:`mark_text` can be removed —
        detector-produced entries are kept as the audit trail (use a
        *keep* decision to exclude them instead).

        Args:
            detection_id: Id of the manual entry to remove.

        Returns:
            ``True`` if the entry existed, was manual, and was removed.
        """
        entry = self.plan.entry_by_id(detection_id)
        if entry is None or entry.detection.detector_name != "manual":
            return False
        self.plan.entries.remove(entry)
        return True

    @staticmethod
    def _char_range_bbox(block: TextBlock, start: int, end: int) -> BoundingBox:
        """Bounding box for a character range of ``block.text``.

        Unlike :meth:`TextBlock.bbox_for_span`, offsets are aligned to
        ``block.text`` (which joins words with separators) by locating
        each word in the text, and partially covered words are clipped
        horizontally in proportion to the covered characters.
        """
        if not block.spans:
            return block.bbox

        x0 = y0 = float("inf")
        x1 = y1 = float("-inf")
        found = False
        pos = 0
        for span in block.spans:
            if not span.text:
                continue
            offset = block.text.find(span.text, pos)
            if offset < 0:
                offset = pos
            pos = offset + len(span.text)
            overlap_start = max(start, offset)
            overlap_end = min(end, offset + len(span.text))
            if overlap_start >= overlap_end:
                continue
            found = True
            width = span.bbox.x1 - span.bbox.x0
            frac_start = (overlap_start - offset) / len(span.text)
            frac_end = (overlap_end - offset) / len(span.text)
            x0 = min(x0, span.bbox.x0 + frac_start * width)
            x1 = max(x1, span.bbox.x0 + frac_end * width)
            y0 = min(y0, span.bbox.y0)
            y1 = max(y1, span.bbox.y1)

        if not found:
            return block.bbox
        return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)

    def page_png(self, page_number: int) -> bytes:
        """Rendered PNG for a page (cached per session)."""
        if page_number not in self._page_cache:
            image = render_page_image(self.pdf_path, page_number, dpi=self.dpi)
            self._page_cache[page_number] = image.png_bytes
        return self._page_cache[page_number]

    def preview_page_png(
        self,
        page_number: int,
        *,
        redaction_type: RedactionType = RedactionType.REPLACE,
    ) -> bytes:
        """Rendered PNG of a page with the current plan's redactions applied.

        Applies the plan to an in-memory copy (undecided entries follow
        their suggestion, like :meth:`apply`) so the reviewer sees exactly
        what the export will look like — the source PDF is untouched.

        The redacted PDF is cached and rebuilt only when a decision or
        mark changes between requests.

        Args:
            page_number: 1-based page number.
            redaction_type: Visual redaction style to preview.

        Returns:
            PNG bytes of the previewed page.

        Raises:
            ValueError: If *page_number* is out of range.
        """
        key = hash(
            (
                redaction_type.value,
                tuple(
                    (e.detection_id, e.decision.value if e.decision else "")
                    for e in self.plan.entries
                ),
            )
        )
        if self._preview_pdf is None or self._preview_key != key:
            detections = self.plan.resolve(accept_suggestions=True)
            redaction_plan = RedactionPlanner().plan(
                self.document, detections, default_type=redaction_type
            )
            self._preview_pdf = PDFRenderer.render_bytes(self.pdf_path.read_bytes(), redaction_plan)
            self._preview_key = key
        return render_page_image_bytes(self._preview_pdf, page_number, dpi=self.dpi).png_bytes

    def save_plan(self) -> Path:
        """Persist the review plan (with decisions) next to the PDF."""
        self.plan_file_path.write_text(self.plan.model_dump_json(indent=2), encoding="utf-8")
        return self.plan_file_path

    def apply(
        self,
        output_path: Path | None = None,
        *,
        redaction_type: RedactionType = RedactionType.REPLACE,
    ) -> tuple[Path, int]:
        """Apply the reviewed plan and render the redacted PDF.

        Undecided entries follow their suggestion; unresolved *ask*
        entries are redacted (privacy-first). The plan (with decisions)
        is saved alongside as the audit record.

        Args:
            output_path: Target path; defaults to ``<name>.redacted.pdf``.
            redaction_type: Visual redaction style.

        Returns:
            ``(output_path, redaction_count)``.
        """
        if output_path is None:
            output_path = self.pdf_path.with_name(f"{self.pdf_path.stem}.redacted.pdf")

        detections = self.plan.resolve(accept_suggestions=True)
        redaction_plan = RedactionPlanner().plan(
            self.document, detections, default_type=redaction_type
        )
        out = PDFRenderer().render(self.pdf_path, output_path, redaction_plan)
        self.save_plan()
        return Path(out), redaction_plan.total_redactions
