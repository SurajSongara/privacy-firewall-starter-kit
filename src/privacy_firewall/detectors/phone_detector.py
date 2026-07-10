from __future__ import annotations

import re

from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.detectors.utils import is_containment_duplicate, is_in_slash_token
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import Span

PHONE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\+\d{1,3}[-.\s]?\d{4,14}"),
    re.compile(r"\b0\d{10}\b"),
    re.compile(r"\d{3}[-.\s]\d{3}[-.\s]\d{4}"),
    re.compile(r"\d{4}[-.\s]\d{3}[-.\s]\d{3}"),
    re.compile(r"\d{5}[-.\s]\d{5}"),
    re.compile(r"\b\d{10}\b"),
]
"""List of regex patterns covering common phone number formats."""


class PhoneDetector(BaseDetector):
    """Detector that identifies phone numbers in document text."""

    @property
    def name(self) -> str:
        """Human-readable detector name."""
        return "phone"

    def scan(self, document: Document, *, values_only: bool = False) -> list[Detection]:
        """Scan a document for phone numbers.

        Iterates over all text blocks and all PHONE_PATTERNS, validates each
        match, deduplicates by normalized digits, and yields a Detection.

        Args:
            document: The document to scan.
            values_only: If ``True``, use per-span bounding boxes for
                precise value-only redaction.

        Returns:
            A list of Detection objects for each valid phone number found.
        """
        detections: list[Detection] = []

        for page in document.pages:
            for block in page.blocks:
                if not isinstance(block, TextBlock):
                    continue

                for pattern in PHONE_PATTERNS:
                    for match in pattern.finditer(block.text):
                        raw = match.group()
                        if not self._validate_phone(raw):
                            continue
                        if is_in_slash_token(block.text, match.start(), match.end()):
                            continue
                        normalized = re.sub(r"[^\d]", "", raw)
                        if is_containment_duplicate(detections, normalized):
                            continue

                        match_bbox = (
                            block.bbox_for_span(match.start(), match.end())
                            if values_only
                            else block.bbox
                        )

                        detections.append(
                            Detection(
                                detector_name=self.name,
                                detection_type="PHONE",
                                text=raw,
                                span=Span(start=match.start(), end=match.end()),
                                bbox=match_bbox,
                                page_number=page.page_number,
                                confidence=self._resolve_confidence(raw),
                            )
                        )

        return detections

    @staticmethod
    def _validate_phone(raw: str) -> bool:
        """Validate a phone number by digit count and leading digit rules.

        Args:
            raw: The raw phone number string.

        Returns:
            True if the number has 10-15 digits and meets country-code rules.
        """
        digits_only = re.sub(r"[^\d]", "", raw)
        if len(digits_only) < 10 or len(digits_only) > 15:
            return False
        if len(digits_only) == 10 and digits_only[0] not in "6789":
            return False
        return True

    @staticmethod
    def _resolve_confidence(raw: str) -> float:
        """Return a confidence score based on phone number format.

        Args:
            raw: The raw phone number string.

        Returns:
            A confidence float between 0.0 and 1.0.
        """
        digits_only = re.sub(r"[^\d]", "", raw)
        if len(digits_only) == 10:
            return 0.85
        if raw.startswith("+") or raw.startswith("0"):
            return 0.9
        return 0.7


