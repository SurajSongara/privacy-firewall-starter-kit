import pytest
from pydantic import ValidationError

from privacy_firewall.models.blocks import BlockType, ImageBlock, TableBlock, TextBlock
from privacy_firewall.models.geometry import BoundingBox


def _bbox() -> BoundingBox:
    return BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=50.0)


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
