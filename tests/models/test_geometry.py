import pytest
from pydantic import ValidationError

from privacy_firewall.models.geometry import BoundingBox, Span


class TestBoundingBox:
    def test_create_valid(self) -> None:
        bbox = BoundingBox(x0=10.0, y0=20.0, x1=100.0, y1=200.0)
        assert bbox.x0 == 10.0
        assert bbox.y0 == 20.0
        assert bbox.x1 == 100.0
        assert bbox.y1 == 200.0

    def test_immutable(self) -> None:
        bbox = BoundingBox(x0=0.0, y0=0.0, x1=10.0, y1=10.0)
        with pytest.raises(ValidationError):
            bbox.x0 = 5.0  # type: ignore[misc]

    def test_x1_must_exceed_x0(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x0=10.0, y0=0.0, x1=10.0, y1=20.0)

    def test_x1_less_than_x0(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x0=10.0, y0=0.0, x1=5.0, y1=20.0)

    def test_y1_must_exceed_y0(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x0=0.0, y0=10.0, x1=20.0, y1=10.0)

    def test_y1_less_than_y0(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x0=0.0, y0=10.0, x1=20.0, y1=5.0)


class TestSpan:
    def test_create_valid(self) -> None:
        span = Span(start=0, end=10)
        assert span.start == 0
        assert span.end == 10

    def test_immutable(self) -> None:
        span = Span(start=0, end=10)
        with pytest.raises(ValidationError):
            span.start = 5  # type: ignore[misc]

    def test_end_must_exceed_start(self) -> None:
        with pytest.raises(ValidationError):
            Span(start=5, end=5)

    def test_end_less_than_start(self) -> None:
        with pytest.raises(ValidationError):
            Span(start=10, end=5)

    def test_start_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            Span(start=-1, end=5)
