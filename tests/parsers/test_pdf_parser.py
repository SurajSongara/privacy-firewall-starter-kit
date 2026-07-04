import fitz

from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.document import Document
from privacy_firewall.parsers.pdf_parser import PDFParser


def _make_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Hello World", fontsize=12)
    page.insert_text((50, 100), "Line two", fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def _make_two_page_pdf() -> bytes:
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((50, 50), "Page one", fontsize=12)
    page2 = doc.new_page()
    page2.insert_text((50, 50), "Page two", fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


class TestPDFParser:
    def test_parse_bytes_returns_document(self) -> None:
        data = _make_pdf()
        doc = PDFParser.parse_bytes(data)
        assert isinstance(doc, Document)
        assert len(doc.pages) == 1

    def test_parse_bytes_text_blocks(self) -> None:
        data = _make_pdf()
        doc = PDFParser.parse_bytes(data)
        page = doc.pages[0]
        blocks = [b for b in page.blocks if isinstance(b, TextBlock)]
        assert len(blocks) >= 1
        assert blocks[0].page_number == 1

    def test_parse_bytes_content(self) -> None:
        data = _make_pdf()
        doc = PDFParser.parse_bytes(data)
        page = doc.pages[0]
        texts = [b.text for b in page.blocks if isinstance(b, TextBlock)]
        combined = " ".join(texts)
        assert "Hello World" in combined
        assert "Line two" in combined

    def test_parse_bytes_page_dimensions(self) -> None:
        data = _make_pdf()
        doc = PDFParser.parse_bytes(data)
        page = doc.pages[0]
        assert page.width > 0
        assert page.height > 0
        assert page.page_number == 1

    def test_multi_page(self) -> None:
        data = _make_two_page_pdf()
        doc = PDFParser.parse_bytes(data)
        assert len(doc.pages) == 2
        assert doc.pages[0].page_number == 1
        assert doc.pages[1].page_number == 2

    def test_multi_page_content(self) -> None:
        data = _make_two_page_pdf()
        doc = PDFParser.parse_bytes(data)

        page1_texts = [b.text for b in doc.pages[0].blocks if isinstance(b, TextBlock)]
        assert "Page one" in " ".join(page1_texts)

        page2_texts = [b.text for b in doc.pages[1].blocks if isinstance(b, TextBlock)]
        assert "Page two" in " ".join(page2_texts)

    def test_blocks_have_bounding_boxes(self) -> None:
        data = _make_pdf()
        doc = PDFParser.parse_bytes(data)
        for block in doc.pages[0].blocks:
            assert block.bbox.x0 >= 0
            assert block.bbox.y0 >= 0
            assert block.bbox.x1 > block.bbox.x0
            assert block.bbox.y1 > block.bbox.y0

    def test_preserves_reading_order(self) -> None:
        data = _make_pdf()
        doc = PDFParser.parse_bytes(data)
        texts = [b.text for b in doc.pages[0].blocks if isinstance(b, TextBlock)]
        if len(texts) >= 2:
            assert texts[0] == "Hello World"
            assert texts[1] == "Line two"
