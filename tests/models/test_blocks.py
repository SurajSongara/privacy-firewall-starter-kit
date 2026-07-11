import pytest
from pydantic import ValidationError

from privacy_firewall.models.blocks import BlockType, ImageBlock, TableBlock, TextBlock, TextSpan
from privacy_firewall.models.geometry import BoundingBox


def _bbox() -> BoundingBox:
    return BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=50.0)


def _word_block() -> TextBlock:
    # Three 5-char words, 50pt wide each, separated by single spaces:
    # text offsets 0-5 "alpha", 6-11 "bravo", 12-18 "charlie".
    words = [("alpha", 0.0), ("bravo", 60.0), ("charlie", 120.0)]
    return TextBlock(
        block_id="b1",
        bbox=BoundingBox(x0=0.0, y0=0.0, x1=190.0, y1=10.0),
        page_number=1,
        confidence=1.0,
        text=" ".join(w for w, _ in words),
        spans=[
            TextSpan(
                text=w,
                bbox=BoundingBox(x0=x, y0=0.0, x1=x + len(w) * 10.0, y1=10.0),
            )
            for w, x in words
        ],
    )


class TestTextBlock:
    def test_create_valid(self) -> None:
        block = TextBlock(block_id="b1", bbox=_bbox(), page_number=1, confidence=0.95, text="Hello")
        assert block.block_id == "b1"
        assert block.block_type == BlockType.TEXT
        assert block.text == "Hello"
        assert block.confidence == 0.95

    def test_immutable(self) -> None:
        block = TextBlock(block_id="b1", bbox=_bbox(), page_number=1, confidence=0.9, text="Hi")
        with pytest.raises(ValidationError):
            block.text = "Changed"  # type: ignore[misc]

    def test_empty_text(self) -> None:
        block = TextBlock(block_id="b1", bbox=_bbox(), page_number=1, confidence=0.8, text="")
        assert block.text == ""


class TestBboxForSpan:
    def test_word_offsets_account_for_separators(self) -> None:
        # "bravo" is at text offset 6-11; a cumulative walk without the
        # separator would misattribute the range to the wrong word.
        block = _word_block()
        box = block.bbox_for_span(6, 11)
        assert box.x0 == 60.0
        assert box.x1 == 110.0

    def test_sub_word_range_clips_proportionally(self) -> None:
        block = _word_block()
        box = block.bbox_for_span(8, 11)  # "avo" — last 3 of 5 chars
        assert box.x0 == pytest.approx(60.0 + 2 / 5 * 50.0)
        assert box.x1 == pytest.approx(110.0)

    def test_range_spanning_words_unions_boxes(self) -> None:
        block = _word_block()
        box = block.bbox_for_span(0, 19)  # "alpha bravo charlie" in full
        assert box.x0 == 0.0
        assert box.x1 == 190.0

    def test_no_overlap_falls_back_to_block_bbox(self) -> None:
        block = _word_block()
        assert block.bbox_for_span(100, 110) == block.bbox

    def test_no_spans_falls_back_to_block_bbox(self) -> None:
        block = TextBlock(block_id="b1", bbox=_bbox(), page_number=1, confidence=1.0, text="hello")
        assert block.bbox_for_span(0, 5) == block.bbox


class TestImageBlock:
    def test_create_valid(self) -> None:
        block = ImageBlock(block_id="i1", bbox=_bbox(), page_number=1, confidence=0.9)
        assert block.block_type == BlockType.IMAGE
        assert block.image_data is None
        assert block.mime_type is None

    def test_with_image_data(self) -> None:
        block = ImageBlock(
            block_id="i1",
            bbox=_bbox(),
            page_number=1,
            confidence=0.9,
            image_data=b"\x89PNG\r\n",
            mime_type="image/png",
        )
        assert block.image_data == b"\x89PNG\r\n"
        assert block.mime_type == "image/png"


class TestTableBlock:
    def test_create_valid(self) -> None:
        block = TableBlock(block_id="t1", bbox=_bbox(), page_number=1, confidence=0.85)
        assert block.block_type == BlockType.TABLE
        assert block.rows == []

    def test_with_rows(self) -> None:
        block = TableBlock(
            block_id="t1",
            bbox=_bbox(),
            page_number=1,
            confidence=0.85,
            rows=[["a", "b"], ["c", "d"]],
        )
        assert len(block.rows) == 2
        assert block.rows[0] == ["a", "b"]


class TestBlockValidation:
    def test_confidence_below_range(self) -> None:
        with pytest.raises(ValidationError):
            TextBlock(block_id="b1", bbox=_bbox(), page_number=1, confidence=-0.1, text="x")

    def test_confidence_above_range(self) -> None:
        with pytest.raises(ValidationError):
            TextBlock(block_id="b1", bbox=_bbox(), page_number=1, confidence=1.1, text="x")

    def test_page_number_zero(self) -> None:
        with pytest.raises(ValidationError):
            TextBlock(block_id="b1", bbox=_bbox(), page_number=0, confidence=0.9, text="x")

    def test_page_number_negative(self) -> None:
        with pytest.raises(ValidationError):
            TextBlock(block_id="b1", bbox=_bbox(), page_number=-1, confidence=0.9, text="x")
