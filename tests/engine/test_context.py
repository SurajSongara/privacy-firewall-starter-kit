from privacy_firewall.engine.context import DROP_FLOOR, ContextScorer
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox, Span


def _document(*block_texts: str) -> Document:
    blocks = [
        TextBlock(
            block_id=f"b{i}",
            bbox=BoundingBox(x0=0.0, y0=float(i * 30), x1=200.0, y1=float(i * 30 + 20)),
            page_number=1,
            confidence=1.0,
            text=text,
        )
        for i, text in enumerate(block_texts)
    ]
    return Document(pages=[Page(page_number=1, width=612.0, height=792.0, blocks=blocks)])


def _detection(
    text: str,
    block_text: str,
    detection_type: str = "AADHAAR",
    confidence: float = 0.95,
) -> Detection:
    start = block_text.index(text)
    return Detection(
        detector_name=detection_type.lower(),
        detection_type=detection_type,
        text=text,
        span=Span(start=start, end=start + len(text)),
        bbox=BoundingBox(x0=0.0, y0=0.0, x1=200.0, y1=20.0),
        page_number=1,
        confidence=confidence,
    )


class TestContextScorer:
    def setup_method(self) -> None:
        self.scorer = ContextScorer()

    def test_positive_label_on_same_line_promotes(self) -> None:
        block = "Aadhaar No: 234512341234"
        doc = _document(block)
        d = _detection("234512341234", block, confidence=0.85)
        [scored] = self.scorer.apply(doc, [d])
        assert scored.confidence > 0.85
        assert any("aadhaar" in r for r in scored.reasons)

    def test_negative_label_on_same_line_demotes(self) -> None:
        block = "UTR 234512341234 transfer completed"
        doc = _document(block)
        d = _detection("234512341234", block, confidence=0.95)
        [scored] = self.scorer.apply(doc, [d])
        assert scored.confidence < 0.95
        assert any("utr" in r for r in scored.reasons)

    def test_demoted_below_floor_is_dropped(self) -> None:
        block = "Txn Ref 234512341234"
        doc = _document(block)
        d = _detection("234512341234", block, confidence=DROP_FLOOR + 0.05)
        assert self.scorer.apply(doc, [d]) == []

    def test_bare_phone_in_reference_context_is_dropped(self) -> None:
        # A bare 10-digit number on a UTR/Ref line is a transaction
        # reference — hard-dropped, not parked in the ask band.
        for block in ("UTR: 7987465071", "Ref ID: 8223027920"):
            doc = _document(block)
            d = _detection(block.split()[-1], block, detection_type="PHONE", confidence=0.85)
            assert self.scorer.apply(doc, [d]) == [], block

    def test_prefixed_phone_in_reference_context_keeps_soft_penalty(self) -> None:
        # An explicit dialling prefix is format evidence — only demote.
        block = "UTR mentioned, call +91-7987465071"
        doc = _document(block)
        d = _detection("+91-7987465071", block, detection_type="PHONE", confidence=0.9)
        [scored] = self.scorer.apply(doc, [d])
        assert 0 < scored.confidence < 0.9

    def test_phone_positive_label_beats_reference_context(self) -> None:
        block = "Mobile: 7987465071 (txn ref 12345)"
        doc = _document(block)
        d = _detection("7987465071", block, detection_type="PHONE", confidence=0.85)
        [scored] = self.scorer.apply(doc, [d])
        assert scored.confidence > 0.85

    def test_positive_beats_negative_at_same_proximity(self) -> None:
        block = "Aadhaar ref: 234512341234"
        doc = _document(block)
        d = _detection("234512341234", block, confidence=0.80)
        [scored] = self.scorer.apply(doc, [d])
        assert scored.confidence > 0.80

    def test_adjacent_block_label_promotes(self) -> None:
        label_block = "Aadhaar Number"
        value_block = "234512341234"
        doc = _document(label_block, value_block)
        d = _detection("234512341234", value_block, confidence=0.80)
        d = d.model_copy(
            update={"bbox": BoundingBox(x0=0.0, y0=30.0, x1=200.0, y1=50.0)}
        )
        [scored] = self.scorer.apply(doc, [d])
        assert scored.confidence > 0.80
        assert any("surrounding" in r for r in scored.reasons)

    def test_negative_in_adjacent_block_demotes(self) -> None:
        label_block = "Transaction Reference"
        value_block = "234512341234"
        doc = _document(label_block, value_block)
        d = _detection("234512341234", value_block, confidence=0.95)
        d = d.model_copy(
            update={"bbox": BoundingBox(x0=0.0, y0=30.0, x1=200.0, y1=50.0)}
        )
        [scored] = self.scorer.apply(doc, [d])
        assert scored.confidence < 0.95

    def test_type_without_lexicon_unchanged(self) -> None:
        block = "Txn Ref email: john@example.com"
        doc = _document(block)
        d = _detection("john@example.com", block, detection_type="EMAIL", confidence=0.9)
        [scored] = self.scorer.apply(doc, [d])
        assert scored == d

    def test_no_label_context_unchanged(self) -> None:
        block = "some text 234512341234 more text"
        doc = _document(block)
        d = _detection("234512341234", block, confidence=0.95)
        [scored] = self.scorer.apply(doc, [d])
        assert scored.confidence == 0.95

    def test_normalized_text_still_locates_block(self) -> None:
        block = "Aadhaar: 2345 1234 1234"
        doc = _document(block)
        start = block.index("2345")
        d = Detection(
            detector_name="aadhaar",
            detection_type="AADHAAR",
            text="234512341234",
            span=Span(start=start, end=start + len("2345 1234 1234")),
            bbox=BoundingBox(x0=0.0, y0=0.0, x1=200.0, y1=20.0),
            page_number=1,
            confidence=0.85,
        )
        [scored] = self.scorer.apply(doc, [d])
        assert scored.confidence > 0.85

    def test_confidence_clamped_to_one(self) -> None:
        block = "Mobile: 9876543210"
        doc = _document(block)
        d = _detection("9876543210", block, detection_type="PHONE", confidence=0.95)
        [scored] = self.scorer.apply(doc, [d])
        assert scored.confidence == 1.0

    def test_account_near_txn_context_demoted(self) -> None:
        block = "NEFT reference 30524123456789 credited"
        doc = _document(block)
        d = _detection("30524123456789", block, detection_type="ACCOUNT", confidence=0.70)
        [scored] = self.scorer.apply(doc, [d])
        assert scored.confidence < 0.5
        assert any("reference context" in r for r in scored.reasons)
