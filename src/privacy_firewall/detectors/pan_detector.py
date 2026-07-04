from __future__ import annotations

import re

from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import Span

PAN_PATTERN = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")

PAN_STATUS_CODES = frozenset({"P", "C", "H", "F", "A", "T", "B", "L", "J", "G"})


class PANDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "pan"

    def scan(self, document: Document) -> list[Detection]:
        detections: list[Detection] = []

        for page in document.pages:
            for block in page.blocks:
                if not isinstance(block, TextBlock):
                    continue

                for match in PAN_PATTERN.finditer(block.text):
                    pan = match.group()
                    if not self._validate_format(pan):
                        continue

                    detections.append(
                        Detection(
                            detector_name=self.name,
                            detection_type="PAN",
                            text=pan,
                            span=Span(start=match.start(), end=match.end()),
                            bbox=block.bbox,
                            page_number=page.page_number,
                            confidence=0.95,
                        )
                    )

        return detections

    @staticmethod
    def _validate_format(pan: str) -> bool:
        if len(pan) != 10:
            return False
        status = pan[3]
        return status in PAN_STATUS_CODES
