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
    @property
    def name(self) -> str:
        return "aadhaar"

    def scan(self, document: Document) -> list[Detection]:
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

                    detections.append(
                        Detection(
                            detector_name=self.name,
                            detection_type="AADHAAR",
                            text=normalized,
                            span=Span(start=match.start(), end=match.end()),
                            bbox=block.bbox,
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

                    detections.append(
                        Detection(
                            detector_name=self.name,
                            detection_type="AADHAAR",
                            text=normalized,
                            span=Span(start=match.start(), end=match.end()),
                            bbox=block.bbox,
                            page_number=page.page_number,
                            confidence=0.95,
                        )
                    )

        return detections

    @staticmethod
    def _validate_format(aadhaar: str) -> bool:
        if len(aadhaar) != 12:
            return False
        if not aadhaar.isdigit():
            return False
        return True

    @staticmethod
    def _is_duplicate(detections: list[Detection], text: str) -> bool:
        return any(d.text == text for d in detections)
