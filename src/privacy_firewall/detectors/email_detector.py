from __future__ import annotations

import re

from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import Span

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


class EmailDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "email"

    def scan(self, document: Document) -> list[Detection]:
        detections: list[Detection] = []

        for page in document.pages:
            for block in page.blocks:
                if not isinstance(block, TextBlock):
                    continue

                for match in EMAIL_PATTERN.finditer(block.text):
                    email = match.group()
                    if not self._validate_format(email):
                        continue

                    detections.append(
                        Detection(
                            detector_name=self.name,
                            detection_type="EMAIL",
                            text=email,
                            span=Span(start=match.start(), end=match.end()),
                            bbox=block.bbox,
                            page_number=page.page_number,
                            confidence=0.9,
                        )
                    )

        return detections

    @staticmethod
    def _validate_format(email: str) -> bool:
        if len(email) > 254:
            return False
        local, _, domain = email.partition("@")
        if not local or len(local) > 64:
            return False
        if not domain or ".." in domain:
            return False
        return True
