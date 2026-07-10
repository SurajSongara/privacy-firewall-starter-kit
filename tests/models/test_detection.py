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


def _detection(**overrides: object) -> Detection:
    fields: dict[str, object] = {
        "detector_name": "pan",
        "detection_type": "PAN",
        "text": "ABCDE1234F",
        "span": Span(start=0, end=10),
        "bbox": BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=20.0),
        "page_number": 1,
        "confidence": 0.9,
    }
    fields.update(overrides)
    return Detection.model_validate(fields)


class TestDetectionEvidence:
    def test_reasons_default_empty(self) -> None:
        assert _detection().reasons == ()

    def test_reasons_stored(self) -> None:
        d = _detection(reasons=("matches PAN format", "checksum passed"))
        assert d.reasons == ("matches PAN format", "checksum passed")

    def test_detection_id_deterministic(self) -> None:
        assert _detection().detection_id == _detection().detection_id

    def test_detection_id_ignores_detector_confidence_reasons(self) -> None:
        a = _detection(detector_name="pan", confidence=0.9)
        b = _detection(detector_name="regex_pan", confidence=0.5, reasons=("x",))
        assert a.detection_id == b.detection_id

    def test_detection_id_changes_with_text(self) -> None:
        assert _detection(text="FGHIJ5678K").detection_id != _detection().detection_id

    def test_detection_id_changes_with_page(self) -> None:
        assert _detection(page_number=2).detection_id != _detection().detection_id

    def test_detection_id_changes_with_span(self) -> None:
        assert (
            _detection(span=Span(start=5, end=15)).detection_id != _detection().detection_id
        )

    def test_detection_id_changes_with_type(self) -> None:
        assert (
            _detection(detection_type="ACCOUNT").detection_id != _detection().detection_id
        )

    def test_detection_id_serialized(self) -> None:
        dumped = _detection().model_dump()
        assert dumped["detection_id"] == _detection().detection_id
