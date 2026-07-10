"""Tests for the OCR pipeline integration."""
from __future__ import annotations

from privacy_firewall.engine.ocr_pipeline import get_merged_document, get_pipeline_summary
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.geometry import BoundingBox


def _tb(text: str) -> TextBlock:
    return TextBlock(
        block_id="b1",
        bbox=BoundingBox(x0=0, y0=0, x1=100, y1=10),
        page_number=1,
        confidence=1.0,
        text=text,
    )


class TestGetPipelineSummary:
    def test_native(self) -> None:
        assert "Native" in get_pipeline_summary("native")

    def test_ocr(self) -> None:
        assert "OCR" in get_pipeline_summary("ocr")

    def test_hybrid(self) -> None:
        assert "Hybrid" in get_pipeline_summary("hybrid")

    def test_unknown(self) -> None:
        assert "Unknown" in get_pipeline_summary("unknown")


class TestGetMergedDocument:
    def test_native_by_default(self) -> None:
        from pathlib import Path


        pdf = Path("benchmarks/native/sbi_statement_native.pdf")
        doc, source = get_merged_document(pdf)
        assert source == "native"
        assert len(doc.pages) > 0

    def test_native_doc_passed_through(self) -> None:
        from pathlib import Path

        pdf = Path("benchmarks/native/sbi_statement_native.pdf")
        from privacy_firewall.parsers.pdf_parser import PDFParser

        native = PDFParser(pdf).parse()
        doc, source = get_merged_document(pdf, native_doc=native)
        assert source == "native"
        assert doc is native

    def test_auto_mode_native(self) -> None:
        from pathlib import Path

        pdf = Path("benchmarks/native/sbi_statement_native.pdf")
        doc, source = get_merged_document(pdf, auto=True)
        assert source == "native"
        assert len(doc.pages) > 0
