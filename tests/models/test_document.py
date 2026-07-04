import pytest
from pydantic import ValidationError

from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox


def _bbox() -> BoundingBox:
    return BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=50.0)


class TestPage:
    def test_create_valid(self) -> None:
        page = Page(page_number=1, width=612.0, height=792.0)
        assert page.page_number == 1
        assert page.width == 612.0
        assert page.height == 792.0
        assert page.blocks == []

    def test_with_blocks(self) -> None:
        block = TextBlock(block_id="b1", bbox=_bbox(), page_number=1, confidence=0.9, text="Hello")
        page = Page(page_number=1, width=612.0, height=792.0, blocks=[block])
        assert len(page.blocks) == 1
        assert page.blocks[0].block_id == "b1"

    def test_page_number_zero(self) -> None:
        with pytest.raises(ValidationError):
            Page(page_number=0, width=612.0, height=792.0)

    def test_width_zero(self) -> None:
        with pytest.raises(ValidationError):
            Page(page_number=1, width=0.0, height=792.0)

    def test_height_zero(self) -> None:
        with pytest.raises(ValidationError):
            Page(page_number=1, width=612.0, height=0.0)


class TestDocument:
    def test_create_empty(self) -> None:
        doc = Document()
        assert doc.pages == []

    def test_with_pages(self) -> None:
        page = Page(page_number=1, width=612.0, height=792.0)
        doc = Document(pages=[page])
        assert len(doc.pages) == 1
        assert doc.pages[0].page_number == 1

    def test_immutable(self) -> None:
        doc = Document()
        with pytest.raises(ValidationError):
            doc.pages = []  # type: ignore[misc]
