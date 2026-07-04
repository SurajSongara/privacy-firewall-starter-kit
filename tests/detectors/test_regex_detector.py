import re

from privacy_firewall.detectors.regex_detector import RegexDetector
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox


def _bbox() -> BoundingBox:
    return BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=50.0)


def _page(text: str, page_number: int = 1) -> Page:
    block = TextBlock(
        block_id="b1", bbox=_bbox(), page_number=page_number, confidence=1.0, text=text
    )
    return Page(page_number=page_number, width=612.0, height=792.0, blocks=[block])


DEFAULT_PATTERN = re.compile(r"\d{5}")


def _detector(*patterns: str, **kwargs: object) -> RegexDetector:
    compiled = [re.compile(p) for p in patterns] if patterns else [DEFAULT_PATTERN]
    return RegexDetector(
        name=str(kwargs.get("name", "test")),
        detection_type=str(kwargs.get("detection_type", "TEST")),
        patterns=compiled,
    )


class TestRegexDetector:
    def test_no_match(self) -> None:
        detector = _detector()
        doc = Document(pages=[_page("hello world")])
        result = detector.scan(doc)
        assert result == []

    def test_single_match(self) -> None:
        detector = _detector()
        doc = Document(pages=[_page("code 12345 end")])
        result = detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == "12345"
        assert result[0].confidence == 1.0
        assert result[0].detector_name == "test"
        assert result[0].detection_type == "TEST"

    def test_multiple_matches(self) -> None:
        detector = _detector()
        doc = Document(pages=[_page("12345 and 67890")])
        result = detector.scan(doc)
        assert len(result) == 2

    def test_multiple_patterns(self) -> None:
        detector = _detector(r"\d{5}", r"[A-Z]{3}")
        doc = Document(pages=[_page("ABC 12345")])
        result = detector.scan(doc)
        assert len(result) == 2

    def test_custom_confidence(self) -> None:
        detector = RegexDetector(
            name="test", detection_type="TEST",
            patterns=[DEFAULT_PATTERN], confidence=0.85,
        )
        doc = Document(pages=[_page("12345")])
        result = detector.scan(doc)
        assert result[0].confidence == 0.85

    def test_priority(self) -> None:
        detector = RegexDetector(
            name="test", detection_type="TEST",
            patterns=[DEFAULT_PATTERN], priority=10,
        )
        assert detector.priority == 10

    def test_default_priority(self) -> None:
        detector = _detector()
        assert detector.priority == 0

    def test_span_correct(self) -> None:
        detector = _detector()
        doc = Document(pages=[_page("id: 12345")])
        result = detector.scan(doc)
        assert result[0].span.start == 4
        assert result[0].span.end == 9

    def test_validation_hook_rejects(self) -> None:
        def validate(text: str) -> float | None:
            return None

        detector = RegexDetector(
            name="test", detection_type="TEST",
            patterns=[DEFAULT_PATTERN], validate=validate,
        )
        doc = Document(pages=[_page("12345")])
        result = detector.scan(doc)
        assert result == []

    def test_validation_hook_adjusts_confidence(self) -> None:
        def validate(text: str) -> float | None:
            return 0.5

        detector = RegexDetector(
            name="test", detection_type="TEST",
            patterns=[DEFAULT_PATTERN], validate=validate,
        )
        doc = Document(pages=[_page("12345")])
        result = detector.scan(doc)
        assert result[0].confidence == 0.5

    def test_multiple_pages(self) -> None:
        detector = _detector()
        doc = Document(
            pages=[_page("12345", page_number=1), _page("67890", page_number=2)]
        )
        result = detector.scan(doc)
        assert len(result) == 2
        assert result[0].page_number == 1
        assert result[1].page_number == 2

    def test_bbox_from_block(self) -> None:
        detector = _detector()
        doc = Document(pages=[_page("12345")])
        result = detector.scan(doc)
        assert result[0].bbox == _bbox()
