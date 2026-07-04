from __future__ import annotations

import time
from dataclasses import dataclass, field

from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document


@dataclass
class DetectorRun:
    detector_name: str
    detection_count: int
    duration_ms: float


@dataclass
class DetectionResult:
    detections: list[Detection] = field(default_factory=list)
    runs: list[DetectorRun] = field(default_factory=list)

    @property
    def total_detections(self) -> int:
        return len(self.detections)

    @property
    def detectors_run(self) -> list[str]:
        return [r.detector_name for r in self.runs]

    def merge(self, other: DetectionResult) -> None:
        self.detections.extend(other.detections)
        self.runs.extend(other.runs)

    @staticmethod
    def from_detections(
        detector_name: str,
        detections: list[Detection],
        duration_ms: float,
    ) -> DetectionResult:
        return DetectionResult(
            detections=detections,
            runs=[
                DetectorRun(
                    detector_name=detector_name,
                    detection_count=len(detections),
                    duration_ms=duration_ms,
                )
            ],
        )


def timed_scan(detector: BaseDetector, document: Document) -> DetectionResult:
    start = time.perf_counter()
    detections = detector.scan(document)
    elapsed = (time.perf_counter() - start) * 1000
    return DetectionResult.from_detections(
        detector_name=detector.name,
        detections=detections,
        duration_ms=elapsed,
    )
