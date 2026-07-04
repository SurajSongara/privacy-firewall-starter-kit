from __future__ import annotations

import re

from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import Span

AADHAAR_CONTINUOUS = re.compile(r"(?<!\d)\d{12}(?!\d)")
AADHAAR_FORMATTED = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")


class AadhaarDetector(BaseDetector):
    """Detector for Indian Aadhaar (12-digit) identifiers.

    Matches both formatted (``1234 5678 9012`` / ``1234-5678-9012``)
    and continuous (``123456789012``) representations, normalises them,
    and deduplicates results.
    """

    @property
    def name(self) -> str:
        """Human-readable detector name."""
        return "aadhaar"

    def scan(self, document: Document, *, values_only: bool = False) -> list[Detection]:
        """Scan every text block for Aadhaar patterns.

        Args:
            document: The document to scan.
            values_only: If ``True``, use per-span bounding boxes for
                precise value-only redaction.

        Returns:
            A list of Detection instances for every unique valid Aadhaar.
        """
        detections: list[Detection] = []

        for page in document.pages:
            for block in page.blocks:
                if not isinstance(block, TextBlock):
                    continue

                for match in AADHAAR_FORMATTED.finditer(block.text):
                    raw = match.group()
                    normalized = re.sub(r"[\s-]", "", raw)
                    if not self._validate_format(normalized):
                        continue
                    if self._is_duplicate(detections, normalized):
                        continue

                    match_bbox = (
                        block.bbox_for_span(match.start(), match.end())
                        if values_only
                        else block.bbox
                    )

                    detections.append(
                        Detection(
                            detector_name=self.name,
                            detection_type="AADHAAR",
                            text=normalized,
                            span=Span(start=match.start(), end=match.end()),
                            bbox=match_bbox,
                            page_number=page.page_number,
                            confidence=0.95,
                        )
                    )

                for match in AADHAAR_CONTINUOUS.finditer(block.text):
                    normalized = match.group()
                    if not self._validate_format(normalized):
                        continue
                    if self._is_duplicate(detections, normalized):
                        continue

                    match_bbox = (
                        block.bbox_for_span(match.start(), match.end())
                        if values_only
                        else block.bbox
                    )

                    detections.append(
                        Detection(
                            detector_name=self.name,
                            detection_type="AADHAAR",
                            text=normalized,
                            span=Span(start=match.start(), end=match.end()),
                            bbox=match_bbox,
                            page_number=page.page_number,
                            confidence=0.95,
                        )
                    )

        return detections

    @staticmethod
    def _validate_format(aadhaar: str) -> bool:
        """Verify the Aadhaar string is exactly 12 digits.

        Args:
            aadhaar: The normalised Aadhaar string to validate.

        Returns:
            ``True`` if the string is 12 digits long.
        """
        if len(aadhaar) != 12:
            return False
        if not aadhaar.isdigit():
            return False
        return True

    @staticmethod
    def _is_duplicate(detections: list[Detection], text: str) -> bool:
        """Check if an Aadhaar text already exists in the result list.

        Args:
            detections: The current list of detections.
            text: The Aadhaar text to check for.

        Returns:
            ``True`` if *text* is already present among the detections.
        """
        return any(d.text == text for d in detections)
