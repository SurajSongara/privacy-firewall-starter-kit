import pytest
from pydantic import ValidationError

from privacy_firewall.models.detection import Detection
from privacy_firewall.models.geometry import BoundingBox, Span


class TestDetection:
    def test_create_valid(self) -> None:
        detection = Detection(
            detector_name="regex_pan",
            detection_type="PAN",
            text="ABCDE1234F",
            span=Span(start=0, end=10),
            bbox=BoundingBox(x0=10.0, y0=20.0, x1=100.0, y1=40.0),
            page_number=1,
            confidence=0.98,
        )
        assert detection.detector_name == "regex_pan"
        assert detection.detection_type == "PAN"
        assert detection.text == "ABCDE1234F"
        assert detection.confidence == 0.98

    def test_immutable(self) -> None:
        detection = Detection(
            detector_name="test",
            detection_type="TEST",
            text="abc",
            span=Span(start=0, end=3),
            bbox=BoundingBox(x0=0.0, y0=0.0, x1=10.0, y1=10.0),
            page_number=1,
            confidence=0.5,
        )
        with pytest.raises(ValidationError):
            detection.confidence = 0.9  # type: ignore[misc]

    def test_confidence_below_range(self) -> None:
        with pytest.raises(ValidationError):
            Detection(
                detector_name="test",
                detection_type="TEST",
                text="abc",
                span=Span(start=0, end=3),
                bbox=BoundingBox(x0=0.0, y0=0.0, x1=10.0, y1=10.0),
                page_number=1,
                confidence=-0.1,
            )

    def test_confidence_above_range(self) -> None:
        with pytest.raises(ValidationError):
            Detection(
                detector_name="test",
                detection_type="TEST",
                text="abc",
                span=Span(start=0, end=3),
                bbox=BoundingBox(x0=0.0, y0=0.0, x1=10.0, y1=10.0),
                page_number=1,
                confidence=1.1,
            )
