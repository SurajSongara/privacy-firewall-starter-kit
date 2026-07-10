from __future__ import annotations

import re

from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.detectors.utils import is_exact_duplicate, is_in_slash_token
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import Span

AADHAAR_CONTINUOUS = re.compile(r"(?<!\d)\d{12}(?!\d)")
AADHAAR_FORMATTED = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")

# Verhoeff algorithm tables for Aadhaar checksum validation
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


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
                    if is_in_slash_token(block.text, match.start(), match.end()):
                        continue
                    if is_exact_duplicate(detections, normalized):
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
                            reasons=(
                                "matches 12-digit Aadhaar format",
                                "Verhoeff checksum passed",
                            ),
                        )
                    )

                for match in AADHAAR_CONTINUOUS.finditer(block.text):
                    normalized = match.group()
                    if not self._validate_format(normalized):
                        continue
                    if is_in_slash_token(block.text, match.start(), match.end()):
                        continue
                    if is_exact_duplicate(detections, normalized):
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
                            reasons=(
                                "matches 12-digit Aadhaar format",
                                "Verhoeff checksum passed",
                            ),
                        )
                    )

        return detections

    @staticmethod
    def _validate_format(aadhaar: str) -> bool:
        """Verify the Aadhaar string is exactly 12 digits with valid Verhoeff checksum.

        Args:
            aadhaar: The normalised Aadhaar string to validate.

        Returns:
            ``True`` if the string is 12 digits long and has a valid checksum.
        """
        if len(aadhaar) != 12:
            return False
        if not aadhaar.isdigit():
            return False
        # UIDAI never issues Aadhaar numbers starting with 0 or 1
        if aadhaar[0] in "01":
            return False
        # Validate Verhoeff checksum
        return AadhaarDetector._verhoeff_check(aadhaar)

    @staticmethod
    def _verhoeff_check(num: str) -> bool:
        """Validate a number using the Verhoeff checksum algorithm.

        Args:
            num: The number string to validate (including check digit).

        Returns:
            ``True`` if the checksum is valid.
        """
        c = 0
        for i in range(len(num) - 1, -1, -1):
            digit = int(num[i])
            pos = (len(num) - 1 - i) % 8
            c = _VERHOEFF_D[c][_VERHOEFF_P[pos][digit]]
        return c == 0


