"""Tests for the PaddleOCR adapter (using mocked PaddleOCR)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import fitz
import pytest

from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.document import Document
from privacy_firewall.ocr.adapters.paddle import PaddleOCRAdapter


@pytest.fixture(autouse=True)
def _mock_paddleocr() -> None:
    """Mock the entire paddleocr module so tests work without installation."""

    class FakePaddleOCR:
        def __init__(self, **kwargs: object) -> None:
            self._kwargs = kwargs

        def ocr(self, img: bytes, **kwargs: object) -> list[list[list[object]]]:
            return [
                [
                    [[[10, 20], [100, 20], [100, 40], [10, 40]], ("Hello", 0.95)],
                    [[[120, 20], [200, 20], [200, 40], [120, 40]], ("World", 0.92)],
                ],
            ]

    fake_module = MagicMock()
    fake_module.PaddleOCR = FakePaddleOCR
    sys.modules["paddleocr"] = fake_module
    yield
    sys.modules.pop("paddleocr", None)


@pytest.fixture
def sample_pdf() -> bytes:
    """Generate a tiny text PDF for testing the adapter."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(50, 100), "Hello World")
    data = doc.tobytes()
    doc.close()
    return data


class TestPaddleOCRAdapter:
    def test_name(self) -> None:
        assert PaddleOCRAdapter.name == "paddleocr"

    def test_default_dpi(self) -> None:
        adapter = PaddleOCRAdapter()
        assert adapter._dpi == 200

    def test_custom_dpi(self) -> None:
        adapter = PaddleOCRAdapter(dpi=300)
        assert adapter._dpi == 300

    def test_custom_lang(self) -> None:
        adapter = PaddleOCRAdapter(lang="ch")
        assert adapter._lang == "ch"

    def test_process_bytes_returns_document(self, sample_pdf: bytes) -> None:
        adapter = PaddleOCRAdapter()
        doc = adapter.process_bytes(sample_pdf)
        assert isinstance(doc, Document)

    def test_process_bytes_has_pages(self, sample_pdf: bytes) -> None:
        adapter = PaddleOCRAdapter()
        doc = adapter.process_bytes(sample_pdf)
        assert len(doc.pages) == 1

    def test_process_bytes_has_text_blocks(self, sample_pdf: bytes) -> None:
        adapter = PaddleOCRAdapter()
        doc = adapter.process_bytes(sample_pdf)
        page = doc.pages[0]
        assert len(page.blocks) == 2
        text_block = page.blocks[0]
        assert isinstance(text_block, TextBlock)
        assert "Hello" in text_block.text

    def test_process_bytes_preserves_text(self, sample_pdf: bytes) -> None:
        adapter = PaddleOCRAdapter()
        doc = adapter.process_bytes(sample_pdf)
        texts = [b.text for p in doc.pages for b in p.blocks if isinstance(b, TextBlock)]
        assert texts == ["Hello", "World"]

    def test_process_bytes_confidence(self, sample_pdf: bytes) -> None:
        adapter = PaddleOCRAdapter()
        doc = adapter.process_bytes(sample_pdf)
        block = doc.pages[0].blocks[0]
        assert isinstance(block, TextBlock)
        assert block.confidence == 0.95

    def test_process_file_path(self, sample_pdf: bytes, tmp_path: Path) -> None:
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(sample_pdf)
        adapter = PaddleOCRAdapter()
        doc = adapter.process(str(pdf_path))
        assert isinstance(doc, Document)
        assert len(doc.pages) == 1

    def test_bbox_scaled_correctly(self, sample_pdf: bytes) -> None:
        adapter = PaddleOCRAdapter(dpi=200)
        doc = adapter.process_bytes(sample_pdf)
        block = doc.pages[0].blocks[0]
        assert isinstance(block, TextBlock)
        bbox = block.bbox
        assert bbox.x0 < bbox.x1
        assert bbox.y0 < bbox.y1
        assert bbox.x0 >= 0
        assert bbox.y0 >= 0

    def test_multi_page_pdf(self) -> None:
        doc = fitz.open()
        doc.new_page()
        doc.new_page()
        doc.new_page()
        data = doc.tobytes()
        doc.close()
        adapter = PaddleOCRAdapter()
        result = adapter.process_bytes(data)
        assert len(result.pages) == 3

    def test_bbox_clipped_to_page(self) -> None:
        adapter = PaddleOCRAdapter(dpi=200)
        mock_doc = fitz.open()
        mock_doc.new_page()
        data = mock_doc.tobytes()
        mock_doc.close()
        result = adapter.process_bytes(data)
        for page in result.pages:
            for block in page.blocks:
                if isinstance(block, TextBlock):
                    assert block.bbox.x0 >= 0
                    assert block.bbox.y0 >= 0

    def test_engine_lazy_initialised(self) -> None:
        adapter = PaddleOCRAdapter()
        assert adapter._ocr is None
        adapter._get_engine()
        assert adapter._ocr is not None

    def test_engine_cached(self) -> None:
        adapter = PaddleOCRAdapter()
        e1 = adapter._get_engine()
        e2 = adapter._get_engine()
        assert e1 is e2

    def test_import_error_when_not_installed(self) -> None:
        doc = fitz.open()
        doc.new_page()
        pdf_bytes = doc.tobytes()
        doc.close()
        saved = sys.modules.pop("paddleocr", None)
        try:
            adapter = PaddleOCRAdapter()
            with pytest.raises(ImportError, match="paddleocr is not installed"):
                adapter.process_bytes(pdf_bytes)
        finally:
            if saved is not None:
                sys.modules["paddleocr"] = saved
