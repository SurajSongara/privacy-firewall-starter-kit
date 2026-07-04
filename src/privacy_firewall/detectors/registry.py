from __future__ import annotations

from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.detectors.result import DetectionResult, timed_scan
from privacy_firewall.models.document import Document


class DetectorRegistry:
    def __init__(self) -> None:
        self._detectors: dict[str, BaseDetector] = {}

    def register(self, detector: BaseDetector) -> None:
        self._detectors[detector.name] = detector

    def unregister(self, name: str) -> None:
        self._detectors.pop(name, None)

    def get(self, name: str) -> BaseDetector | None:
        return self._detectors.get(name)

    @property
    def detectors(self) -> dict[str, BaseDetector]:
        return dict(self._detectors)

    @property
    def detector_names(self) -> list[str]:
        return list(self._detectors)

    def run_all(self, document: Document) -> DetectionResult:
        result = DetectionResult()
        for detector in self._detectors.values():
            dr = timed_scan(detector, document)
            result.merge(dr)
        return result

    def run(self, document: Document, name: str) -> DetectionResult | None:
        detector = self._detectors.get(name)
        if detector is None:
            return None
        return timed_scan(detector, document)
