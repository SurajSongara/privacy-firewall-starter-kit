from privacy_firewall.engine.fusion import (
    FusionEngine,
    FusionResult,
    MergeRecord,
    detector_priority,
    spans_overlap,
)
from privacy_firewall.models.detection import Detection
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
    return Detection(
        detector_name=detector_name,
        detection_type=detection_type,
        text=text,
        span=Span(start=start, end=end),
        bbox=BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=20.0),
        page_number=page_number,
        confidence=confidence,
    )


class TestDetectorPriority:
    def test_known_detector(self) -> None:
        assert detector_priority("pan") == 5
        assert detector_priority("aadhaar") == 5
        assert detector_priority("email") == 5
        assert detector_priority("phone") == 5
        assert detector_priority("upi") == 5

    def test_unknown_detector_defaults_to_heuristic(self) -> None:
        assert detector_priority("unknown") == 3

    def test_llm_tier(self) -> None:
        pri = detector_priority("ner_model")
        assert pri > 0


class TestSpansOverlap:
    def test_overlapping_spans(self) -> None:
        assert spans_overlap(Span(start=0, end=10), Span(start=5, end=15))

    def test_non_overlapping_spans(self) -> None:
        assert not spans_overlap(Span(start=0, end=10), Span(start=10, end=20))

    def test_one_contains_other(self) -> None:
        assert spans_overlap(Span(start=0, end=20), Span(start=5, end=15))

    def test_identical_spans(self) -> None:
        assert spans_overlap(Span(start=5, end=15), Span(start=5, end=15))

    def test_reverse_order(self) -> None:
        assert spans_overlap(Span(start=5, end=15), Span(start=0, end=10))


class TestFusionEngine:
    def setup_method(self) -> None:
        self.engine = FusionEngine()

    def test_empty_input(self) -> None:
        result = self.engine.fuse([])
        assert result.detections == []
        assert result.merge_log == []

    def test_single_detection(self) -> None:
        d = _detection()
        result = self.engine.fuse([d])
        assert result.detections == [d]
        assert result.merge_log == []

    def test_no_overlap_different_positions(self) -> None:
        d1 = _detection(start=0, end=10)
        d2 = _detection(start=20, end=30)
        result = self.engine.fuse([d1, d2])
        assert len(result.detections) == 2
        assert result.merge_log == []

    def test_no_overlap_different_types(self) -> None:
        d1 = _detection(detection_type="PAN", start=0, end=10)
        d2 = _detection(detection_type="PHONE", start=5, end=15)
        result = self.engine.fuse([d1, d2])
        assert len(result.detections) == 2
        assert result.merge_log == []

    def test_no_overlap_different_pages(self) -> None:
        d1 = _detection(start=0, end=10, page_number=1)
        d2 = _detection(start=0, end=10, page_number=2)
        result = self.engine.fuse([d1, d2])
        assert len(result.detections) == 2
        assert result.merge_log == []

    def test_overlap_keeps_higher_confidence(self) -> None:
        d1 = _detection(detector_name="email", confidence=0.7, start=0, end=15)
        d2 = _detection(detector_name="email", confidence=0.95, start=5, end=15)
        result = self.engine.fuse([d1, d2])
        assert len(result.detections) == 1
        assert result.detections[0].confidence == 0.95
        assert len(result.merge_log) == 1
        assert result.merge_log[0].kept == d2
        assert result.merge_log[0].merged == [d1]

    def test_overlap_keeps_higher_priority(self) -> None:
        d1 = _detection(
            detector_name="ner_model",
            detection_type="PAN",
            confidence=0.95,
            start=0,
            end=10,
        )
        d2 = _detection(
            detector_name="pan",
            detection_type="PAN",
            confidence=0.85,
            start=0,
            end=10,
        )
        result = self.engine.fuse([d1, d2])
        assert len(result.detections) == 1
        assert result.detections[0].detector_name == "pan"

    def test_overlap_same_priority_and_confidence_keeps_first(self) -> None:
        d1 = _detection(detector_name="email", confidence=0.9, start=0, end=15)
        d2 = _detection(detector_name="email", confidence=0.9, start=5, end=15)
        result = self.engine.fuse([d1, d2])
        assert len(result.detections) == 1
        assert result.detections[0] == d1
        assert result.merge_log[0].kept == d1

    def test_one_span_contains_another(self) -> None:
        d1 = _detection(confidence=0.8, start=0, end=20)
        d2 = _detection(confidence=0.95, start=5, end=15)
        result = self.engine.fuse([d1, d2])
        assert len(result.detections) == 1
        assert result.detections[0].confidence == 0.95

    def test_adjacent_spans_not_merged(self) -> None:
        d1 = _detection(start=0, end=10)
        d2 = _detection(start=10, end=20)
        result = self.engine.fuse([d1, d2])
        assert len(result.detections) == 2

    def test_chain_overlap(self) -> None:
        d1 = _detection(detector_name="email", confidence=0.7, start=0, end=10)
        d2 = _detection(detector_name="email", confidence=0.8, start=5, end=15)
        d3 = _detection(detector_name="email", confidence=0.95, start=12, end=25)
        result = self.engine.fuse([d1, d2, d3])
        assert len(result.detections) == 1
        assert result.detections[0].confidence == 0.95

    def test_mixed_types_with_overlap(self) -> None:
        d1 = _detection(detection_type="PAN", start=0, end=10)
        d2 = _detection(detection_type="PAN", start=5, end=15)
        d3 = _detection(detection_type="EMAIL", start=5, end=15)
        result = self.engine.fuse([d1, d2, d3])
        assert len(result.detections) == 2

    def test_multiple_pages(self) -> None:
        d1 = _detection(start=0, end=10, page_number=1)
        d2 = _detection(start=5, end=15, page_number=1)
        d3 = _detection(start=0, end=10, page_number=2)
        d4 = _detection(start=5, end=15, page_number=2)
        result = self.engine.fuse([d1, d2, d3, d4])
        assert len(result.detections) == 2

    def test_merge_log_records_all_merges(self) -> None:
        d1 = _detection(detector_name="email", confidence=0.7, start=0, end=10)
        d2 = _detection(detector_name="email", confidence=0.95, start=5, end=15)
        d3 = _detection(detector_name="email", confidence=0.8, start=20, end=30)
        result = self.engine.fuse([d1, d2, d3])
        assert len(result.merge_log) == 1
        entry = result.merge_log[0]
        assert isinstance(entry, MergeRecord)
        assert entry.kept.confidence == 0.95
        assert entry.merged == [d1]
        assert "confidence" in entry.reason

    def test_merge_reason_priority(self) -> None:
        d1 = _detection(
            detector_name="ner_model",
            detection_type="PAN",
            confidence=0.95,
            start=0,
            end=10,
        )
        d2 = _detection(
            detector_name="pan",
            detection_type="PAN",
            confidence=0.85,
            start=5,
            end=15,
        )
        result = self.engine.fuse([d1, d2])
        assert len(result.merge_log) == 1
        assert "priority" in result.merge_log[0].reason

    def test_fusion_result_dataclass(self) -> None:
        result = FusionResult(detections=[], merge_log=[])
        assert result.detections == []
        assert result.merge_log == []
