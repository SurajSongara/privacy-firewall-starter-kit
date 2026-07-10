"""Review session: engine orchestration behind the review UI.

Pure engine code — no web-framework imports — so the session is fully
testable without the ``ui`` extra installed.
"""

from __future__ import annotations

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
    file_sha256,
)
from privacy_firewall.engine.fusion import FusionEngine
from privacy_firewall.engine.ocr_pipeline import get_merged_document, get_pipeline_summary
from privacy_firewall.engine.redaction import RedactionPlanner, RedactionType
from privacy_firewall.policy.models import Policy
from privacy_firewall.renderer.page_images import DEFAULT_DPI, render_page_image
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
    ) -> None:
        """Run the detection pipeline and build the review plan.

        Args:
            pdf_path: The PDF under review.
            policy: Policy providing the suggested actions.
            force_ocr: Force the OCR pipeline.
            auto: Let diagnostics choose the pipeline.
            ocr_provider: Specific OCR engine name.
            dpi: Page-image render resolution.
        """
        self.pdf_path = Path(pdf_path)
        self.policy = policy
        self.dpi = dpi
        self._page_cache: dict[int, bytes] = {}

        self.document, self.source = get_merged_document(
            self.pdf_path, force_ocr=force_ocr, auto=auto, ocr_provider=ocr_provider
        )

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

        detections = registry.run_all(self.document, values_only=True).detections
        detections = ContextScorer().apply(self.document, detections)
        detections = FusionEngine().fuse(detections).detections

        self.plan = DecisionEngine().decide(
            detections,
            policy,
            source_path=str(self.pdf_path),
            source_sha256=file_sha256(self.pdf_path),
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
            "pages": [
                {"page_number": p.page_number, "width": p.width, "height": p.height}
                for p in self.document.pages
            ],
            "entries": [
                {
                    "detection_id": e.detection_id,
                    "type": e.detection.detection_type,
                    "text": e.detection.text,
                    "page_number": e.detection.page_number,
                    "confidence": e.detection.confidence,
                    "bbox": e.detection.bbox.model_dump(),
                    "reasons": list(e.detection.reasons) + list(e.suggestion_reasons),
                    "suggested_action": e.suggested_action.value,
                    "decision": e.decision.value if e.decision else None,
                    "effective_action": e.effective_action.value,
                }
                for e in self.plan.entries
            ],
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

    def page_png(self, page_number: int) -> bytes:
        """Rendered PNG for a page (cached per session)."""
        if page_number not in self._page_cache:
            image = render_page_image(self.pdf_path, page_number, dpi=self.dpi)
            self._page_cache[page_number] = image.png_bytes
        return self._page_cache[page_number]

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
