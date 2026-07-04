from __future__ import annotations

import re
from collections.abc import Callable

from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import Span

ValidationHook = Callable[[str], float | None]


class RegexDetector(BaseDetector):
    def __init__(
        self,
        name: str,
        detection_type: str,
        patterns: list[re.Pattern[str]],
        *,
        validate: ValidationHook | None = None,
        confidence: float = 1.0,
        priority: int = 0,
    ) -> None:
        self._name = name
        self._detection_type = detection_type
        self._patterns = patterns
        self._validate = validate
        self._confidence = confidence
        self._priority = priority

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    def scan(self, document: Document) -> list[Detection]:
        detections: list[Detection] = []

        for page in document.pages:
            for block in page.blocks:
                if not isinstance(block, TextBlock):
                    continue

                for pattern in self._patterns:
                    for match in pattern.finditer(block.text):
                        matched_text = match.group()
                        conf = self._resolve_confidence(matched_text)
                        if conf is None:
                            continue

                        detections.append(
                            Detection(
                                detector_name=self._name,
                                detection_type=self._detection_type,
                                text=matched_text,
                                span=Span(start=match.start(), end=match.end()),
                                bbox=block.bbox,
                                page_number=page.page_number,
                                confidence=conf,
                            )
                        )

        return detections

    def _resolve_confidence(self, matched_text: str) -> float | None:
        if self._validate is not None:
            result = self._validate(matched_text)
            if result is None:
                return None
            return result
        return self._confidence
