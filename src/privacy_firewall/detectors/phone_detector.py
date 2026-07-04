from __future__ import annotations

import re

from privacy_firewall.detectors.base import BaseDetector
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


class PhoneDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "phone"

    def scan(self, document: Document) -> list[Detection]:
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
                        normalized = re.sub(r"[^\d]", "", raw)
                        if self._is_duplicate(detections, normalized):
                            continue

                        detections.append(
                            Detection(
                                detector_name=self.name,
                                detection_type="PHONE",
                                text=raw,
                                span=Span(start=match.start(), end=match.end()),
                                bbox=block.bbox,
                                page_number=page.page_number,
                                confidence=self._resolve_confidence(raw),
                            )
                        )

        return detections

    @staticmethod
    def _validate_phone(raw: str) -> bool:
        digits_only = re.sub(r"[^\d]", "", raw)
        if len(digits_only) < 10 or len(digits_only) > 15:
            return False
        if len(digits_only) == 10 and digits_only[0] not in "6789":
            return False
        return True

    @staticmethod
    def _resolve_confidence(raw: str) -> float:
        digits_only = re.sub(r"[^\d]", "", raw)
        if len(digits_only) == 10:
            return 0.85
        if raw.startswith("+") or raw.startswith("0"):
            return 0.9
        return 0.7

    @staticmethod
    def _is_duplicate(detections: list[Detection], normalized: str) -> bool:
        for d in detections:
            existing = re.sub(r"[^\d]", "", d.text)
            if normalized in existing or existing in normalized:
                return True
        return False
