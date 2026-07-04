from privacy_firewall.detectors.result import DetectionResult, DetectorRun
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.geometry import BoundingBox, Span


def _detection(text: str = "test") -> Detection:
    return Detection(
        detector_name="test",
        detection_type="TEST",
        text=text,
        span=Span(start=0, end=4),
        bbox=BoundingBox(x0=0.0, y0=0.0, x1=10.0, y1=10.0),
        page_number=1,
        confidence=0.9,
    )


class TestDetectorRun:
    def test_create(self) -> None:
        run = DetectorRun(detector_name="pan", detection_count=3, duration_ms=1.5)
        assert run.detector_name == "pan"
        assert run.detection_count == 3
        assert run.duration_ms == 1.5


class TestDetectionResult:
    def test_empty(self) -> None:
        result = DetectionResult()
        assert result.total_detections == 0
        assert result.detectors_run == []

    def test_from_detections(self) -> None:
        detections = [_detection()]
        result = DetectionResult.from_detections("pan", detections, duration_ms=2.0)
        assert result.total_detections == 1
        assert result.detectors_run == ["pan"]
        assert result.runs[0].duration_ms == 2.0

    def test_merge(self) -> None:
        r1 = DetectionResult.from_detections("pan", [_detection("a")], duration_ms=1.0)
        r2 = DetectionResult.from_detections("aadhaar", [_detection("b")], duration_ms=2.0)
        r1.merge(r2)
        assert r1.total_detections == 2
        assert len(r1.runs) == 2
        assert r1.detectors_run == ["pan", "aadhaar"]
