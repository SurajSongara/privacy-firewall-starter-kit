"""Context scoring: adjust detection confidence using surrounding text.

A post-detection, pre-fusion pass. For ambiguous detection types (digit
runs that could be Aadhaar numbers, phone numbers, or account numbers),
nearby label text is strong evidence: "Aadhaar No" promotes, "UTR" or
"Txn Ref" demotes. The pass is pure — ``(Document, detections) → detections``
— and every adjustment is recorded in the detection's ``reasons``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import BoundingBox


@dataclass(frozen=True)
class TypeLexicon:
    """Positive and negative label terms for one detection type."""

    positive: tuple[str, ...]
    negative: tuple[str, ...]


LEXICONS: dict[str, TypeLexicon] = {
    "AADHAAR": TypeLexicon(
        positive=("aadhaar", "aadhar", "uid", "uidai"),
        negative=(
            "utr", "rrn", "ref", "reference", "txn", "transaction",
            "imps", "neft", "rtgs", "cheque", "invoice", "order",
        ),
    ),
    "PHONE": TypeLexicon(
        positive=("phone", "mobile", "mob", "contact", "tel", "whatsapp", "helpline"),
        negative=(
            "utr", "rrn", "ref", "reference", "txn", "transaction",
            "imps", "neft", "rtgs", "cheque", "invoice", "order", "a/c", "account",
        ),
    ),
    "ACCOUNT": TypeLexicon(
        positive=("a/c", "account", "acct", "cif", "customer id", "ckycr"),
        negative=(
            "utr", "rrn", "ref", "reference", "txn", "transaction",
            "imps", "neft", "rtgs", "cheque", "invoice", "order", "bill",
        ),
    ),
}

LINE_POSITIVE_BOOST = 0.10
NEARBY_POSITIVE_BOOST = 0.05
LINE_NEGATIVE_PENALTY = 0.35
NEARBY_NEGATIVE_PENALTY = 0.20

DROP_FLOOR = 0.3
"""Detections demoted below this confidence are dropped entirely."""


def _term_pattern(term: str) -> re.Pattern[str]:
    """Compile a case-insensitive whole-word pattern for a lexicon term."""
    return re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", re.IGNORECASE)


_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def _find_term(text: str, terms: tuple[str, ...]) -> str | None:
    """Return the first lexicon term found in *text*, or ``None``."""
    for term in terms:
        pattern = _PATTERN_CACHE.get(term)
        if pattern is None:
            pattern = _term_pattern(term)
            _PATTERN_CACHE[term] = pattern
        if pattern.search(text):
            return term
    return None


def _bboxes_intersect(a: BoundingBox, b: BoundingBox) -> bool:
    """Return ``True`` if two bounding boxes overlap at all."""
    return not (a.x1 < b.x0 or b.x1 < a.x0 or a.y1 < b.y0 or b.y1 < a.y0)


def _digits(text: str) -> str:
    """Return only the digit characters of *text*."""
    return re.sub(r"\D", "", text)


class ContextScorer:
    """Adjusts detection confidence based on labels in the surrounding text.

    Search order (closest evidence wins): the line containing the match,
    then the rest of the containing block, then vertically adjacent blocks.
    Positive evidence takes precedence over negative at equal proximity —
    when in doubt, keep the detection (privacy-first).
    """

    def apply(self, document: Document, detections: list[Detection]) -> list[Detection]:
        """Return the detections with context-adjusted confidence.

        Detections whose type has no lexicon, or whose source block cannot
        be located, pass through unchanged. Detections demoted below
        ``DROP_FLOOR`` are removed.

        Args:
            document: The document the detections came from.
            detections: Detections to score.

        Returns:
            Context-scored detections (possibly fewer than the input).
        """
        blocks_by_page: dict[int, list[TextBlock]] = {}
        for page in document.pages:
            blocks_by_page[page.page_number] = [
                b for b in page.blocks if isinstance(b, TextBlock)
            ]

        result: list[Detection] = []
        for detection in detections:
            lexicon = LEXICONS.get(detection.detection_type)
            if lexicon is None:
                result.append(detection)
                continue

            page_blocks = blocks_by_page.get(detection.page_number, [])
            block_idx = self._find_source_block(page_blocks, detection)
            if block_idx is None:
                result.append(detection)
                continue

            adjusted = self._score(detection, lexicon, page_blocks, block_idx)
            was_demoted = adjusted.confidence < detection.confidence
            if was_demoted and adjusted.confidence < DROP_FLOOR:
                continue
            result.append(adjusted)

        return result

    @staticmethod
    def _find_source_block(page_blocks: list[TextBlock], detection: Detection) -> int | None:
        """Locate the block whose text contains the detection's span.

        The span indexes into the source block's text; the matched slice is
        compared digit-wise (detectors may store normalised text). Bbox
        intersection breaks ties between candidate blocks.

        Args:
            page_blocks: Text blocks on the detection's page.
            detection: The detection to locate.

        Returns:
            Index of the source block in *page_blocks*, or ``None``.
        """
        candidates: list[int] = []
        for idx, block in enumerate(page_blocks):
            if detection.span.end > len(block.text):
                continue
            slice_ = block.text[detection.span.start : detection.span.end]
            if slice_ == detection.text or (
                _digits(detection.text) != "" and _digits(slice_) == _digits(detection.text)
            ):
                candidates.append(idx)

        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        for idx in candidates:
            if _bboxes_intersect(page_blocks[idx].bbox, detection.bbox):
                return idx
        return candidates[0]

    def _score(
        self,
        detection: Detection,
        lexicon: TypeLexicon,
        page_blocks: list[TextBlock],
        block_idx: int,
    ) -> Detection:
        """Apply the strongest, closest context signal to one detection."""
        block = page_blocks[block_idx]
        line = self._line_around(block.text, detection.span.start, detection.span.end)
        rest_of_block = block.text[: detection.span.start] + block.text[detection.span.end :]
        nearby_parts: list[str] = [rest_of_block]
        if block_idx > 0:
            nearby_parts.append(page_blocks[block_idx - 1].text)
        if block_idx + 1 < len(page_blocks):
            nearby_parts.append(page_blocks[block_idx + 1].text)
        nearby = "\n".join(nearby_parts)

        term = _find_term(line, lexicon.positive)
        if term is not None:
            return self._adjust(detection, LINE_POSITIVE_BOOST, f"near label '{term}'")
        term = _find_term(line, lexicon.negative)
        if term is not None:
            return self._adjust(
                detection, -LINE_NEGATIVE_PENALTY, f"reference context on the same line ('{term}')"
            )
        term = _find_term(nearby, lexicon.positive)
        if term is not None:
            return self._adjust(
                detection, NEARBY_POSITIVE_BOOST, f"label '{term}' in surrounding text"
            )
        term = _find_term(nearby, lexicon.negative)
        if term is not None:
            return self._adjust(
                detection,
                -NEARBY_NEGATIVE_PENALTY,
                f"reference context in surrounding text ('{term}')",
            )
        return detection

    @staticmethod
    def _adjust(detection: Detection, delta: float, reason: str) -> Detection:
        """Return a copy of *detection* with confidence shifted by *delta*."""
        new_confidence = max(0.0, min(1.0, detection.confidence + delta))
        return detection.model_copy(
            update={
                "confidence": new_confidence,
                "reasons": detection.reasons + (reason,),
            }
        )

    @staticmethod
    def _line_around(text: str, start: int, end: int) -> str:
        """Return the line of *text* containing the ``[start, end)`` span."""
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", end)
        if line_end == -1:
            line_end = len(text)
        return text[line_start:line_end]
