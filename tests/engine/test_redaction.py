"""Tests for the redaction planner and related types."""

from privacy_firewall.engine.redaction import (
    Redaction,
    RedactionPlan,
    RedactionPlanner,
    RedactionType,
)
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox, Span


def _detection(
    detector_name: str = "pan",
    detection_type: str = "PAN",
    text: str = "ABCDE1234F",
    start: int = 0,
    end: int = 10,
    confidence: float = 0.9,
    page_number: int = 1,
) -> Detection:
    """Create a Detection fixture for testing."""
    return Detection(
        detector_name=detector_name,
        detection_type=detection_type,
        text=text,
        span=Span(start=start, end=end),
        bbox=BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=20.0),
        page_number=page_number,
        confidence=confidence,
    )


def _document() -> Document:
    """Create a minimal Document fixture for testing."""
    bbox = BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=20.0)
    block = TextBlock(
        block_id="b1",
        bbox=bbox,
        page_number=1,
        confidence=1.0,
        text="My PAN is ABCDE1234F and Aadhaar 123456789012",
    )
    page = Page(page_number=1, width=612.0, height=792.0, blocks=[block])
    return Document(pages=[page])


class TestRedactionType:
    """Verify the RedactionType enum values."""

    def test_values(self) -> None:
        assert RedactionType.REPLACE.value == "replace"
        assert RedactionType.BLACK_BAR.value == "black_bar"
        assert RedactionType.HIGHLIGHT.value == "highlight"


class TestRedaction:
    """Verify the Redaction dataclass."""

    def test_create(self) -> None:
        det = _detection()
        redaction = Redaction(
            detection=det,
            redaction_type=RedactionType.REPLACE,
            replacement_text="[REDACTED]",
            page_number=1,
            span=Span(start=0, end=10),
            bbox=BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=20.0),
        )
        assert redaction.detection == det
        assert redaction.redaction_type == RedactionType.REPLACE
        assert redaction.replacement_text == "[REDACTED]"
        assert redaction.page_number == 1

    def test_default_factory_provides_defaults(self) -> None:
        det = _detection()
        redaction = Redaction(detection=det, redaction_type=RedactionType.REPLACE)
        assert redaction.replacement_text is None
        assert redaction.page_number == 0
        assert redaction.span == Span(start=0, end=1)
        assert redaction.bbox == BoundingBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0)


class TestRedactionPlan:
    """Verify the RedactionPlan dataclass and its helper methods."""

    def test_empty_plan(self) -> None:
        plan = RedactionPlan()
        assert plan.redactions == []
        assert plan.total_redactions == 0

    def test_total_redactions(self) -> None:
        det = _detection()
        redactions = [
            Redaction(detection=det, redaction_type=RedactionType.REPLACE),
            Redaction(detection=det, redaction_type=RedactionType.BLACK_BAR),
        ]
        plan = RedactionPlan(redactions=redactions)
        assert plan.total_redactions == 2

    def test_by_page(self) -> None:
        det1 = _detection(page_number=1)
        det2 = _detection(page_number=2)
        redactions = [
            Redaction(
                detection=det1,
                redaction_type=RedactionType.REPLACE,
                page_number=1,
                span=det1.span,
                bbox=det1.bbox,
            ),
            Redaction(
                detection=det2,
                redaction_type=RedactionType.REPLACE,
                page_number=2,
                span=det2.span,
                bbox=det2.bbox,
            ),
        ]
        plan = RedactionPlan(redactions=redactions)
        assert len(plan.by_page(1)) == 1
        assert len(plan.by_page(2)) == 1
        assert len(plan.by_page(3)) == 0

    def test_by_type(self) -> None:
        det1 = _detection(detection_type="PAN")
        det2 = _detection(detection_type="AADHAAR", text="123456789012")
        redactions = [
            Redaction(
                detection=det1,
                redaction_type=RedactionType.REPLACE,
                page_number=1,
                span=det1.span,
                bbox=det1.bbox,
            ),
            Redaction(
                detection=det2,
                redaction_type=RedactionType.REPLACE,
                page_number=1,
                span=det2.span,
                bbox=det2.bbox,
            ),
        ]
        plan = RedactionPlan(redactions=redactions)
        assert len(plan.by_type("PAN")) == 1
        assert len(plan.by_type("AADHAAR")) == 1
        assert len(plan.by_type("EMAIL")) == 0


class TestRedactionPlanner:
    """Verify the RedactionPlanner produces correct plans."""

    def setup_method(self) -> None:
        self.planner = RedactionPlanner()
        self.doc = _document()

    def test_plan_creates_one_redaction_per_detection(self) -> None:
        detections = [_detection(), _detection(text="DIFFERENT", detection_type="PAN")]
        plan = self.planner.plan(self.doc, detections)
        assert len(plan.redactions) == 2

    def test_plan_default_type_is_replace(self) -> None:
        detections = [_detection()]
        plan = self.planner.plan(self.doc, detections)
        assert plan.redactions[0].redaction_type == RedactionType.REPLACE

    def test_plan_replacement_stars_match_value_length(self) -> None:
        detections = [_detection()]  # text "ABCDE1234F" (10 chars)
        plan = self.planner.plan(self.doc, detections)
        assert plan.redactions[0].replacement_text == "*" * 10

    def test_plan_replacement_stars_are_bounded(self) -> None:
        short = _detection(text="ab")
        long = _detection(text="x" * 80, detection_type="LONG")
        plan = self.planner.plan(self.doc, [short, long])
        assert plan.redactions[0].replacement_text == "***"
        assert plan.redactions[1].replacement_text == "*" * 32

    def test_plan_honours_custom_default_type(self) -> None:
        detections = [_detection()]
        plan = self.planner.plan(self.doc, detections, default_type=RedactionType.BLACK_BAR)
        assert plan.redactions[0].redaction_type == RedactionType.BLACK_BAR

    def test_plan_with_highlight_preserves_original_text(self) -> None:
        detections = [_detection(text="ABCDE1234F")]
        plan = RedactionPlanner.plan_with_highlight(self.doc, detections)
        assert plan.redactions[0].redaction_type == RedactionType.HIGHLIGHT
        assert plan.redactions[0].replacement_text == "ABCDE1234F"

    def test_plan_inherits_detection_metadata(self) -> None:
        detections = [_detection(page_number=2, start=5, end=15)]
        plan = self.planner.plan(self.doc, detections)
        r = plan.redactions[0]
        assert r.page_number == 2
        assert r.span == Span(start=5, end=15)
        assert r.bbox == BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=20.0)

    def test_plan_with_black_bar_static(self) -> None:
        detections = [_detection()]
        plan = RedactionPlanner.plan_with_black_bar(self.doc, detections)
        assert plan.redactions[0].redaction_type == RedactionType.BLACK_BAR

    def test_plan_with_highlight_static(self) -> None:
        detections = [_detection()]
        plan = RedactionPlanner.plan_with_highlight(self.doc, detections)
        assert plan.redactions[0].redaction_type == RedactionType.HIGHLIGHT

    def test_plan_with_replacement_static(self) -> None:
        detections = [_detection()]
        plan = RedactionPlanner.plan_with_replacement(self.doc, detections)
        assert plan.redactions[0].redaction_type == RedactionType.REPLACE

    def test_empty_detections(self) -> None:
        plan = self.planner.plan(self.doc, [])
        assert plan.total_redactions == 0

    def test_multiple_types_in_plan(self) -> None:
        detections = [
            _detection(detection_type="PAN", text="AAAAA1111A"),
            _detection(detection_type="AADHAAR", text="123456789012"),
        ]
        plan = self.planner.plan(self.doc, detections)
        assert len(plan.redactions) == 2
        assert plan.redactions[0].detection.detection_type == "PAN"
        assert plan.redactions[1].detection.detection_type == "AADHAAR"
