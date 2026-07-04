"""Tests for the DocumentAnalyzer."""
from __future__ import annotations

import fitz
import pytest

from privacy_firewall.diagnostics import DiagnosticReport, DocumentAnalyzer, PipelineType


@pytest.fixture
def clean_text_pdf() -> bytes:
    """A PDF with clean extractable text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(50, 100), "Hello world. This is clean text.")
    return doc.tobytes()


@pytest.fixture
def scanned_pdf() -> bytes:
    """A PDF with no text and a large embedded image (simulating a scan)."""
    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, (0, 0, 100, 100))
    page.insert_image(fitz.Rect(0, 0, 100, 100), pixmap=pix)
    return doc.tobytes()


@pytest.fixture
def rotated_pdf() -> bytes:
    """A multi-page PDF where one page is rotated."""
    doc = fitz.open()
    for _ in range(3):
        page = doc.new_page()
        page.insert_text(fitz.Point(50, 100), "Normal page")
    doc[1].set_rotation(90)
    return doc.tobytes()


@pytest.fixture
def multi_image_pdf() -> bytes:
    """A PDF with multiple images per page (high image/page ratio)."""
    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, (0, 0, 50, 50))
    page.insert_image(fitz.Rect(0, 0, 50, 50), pixmap=pix)
    page.insert_image(fitz.Rect(60, 0, 110, 50), pixmap=pix)
    page.insert_image(fitz.Rect(120, 0, 170, 50), pixmap=pix)
    page.insert_image(fitz.Rect(180, 0, 230, 50), pixmap=pix)
    return doc.tobytes()


@pytest.fixture
def garbage_text_pdf() -> bytes:
    """A PDF with low quality text (many null chars + long tokens)."""
    doc = fitz.open()
    page = doc.new_page()
    garbage = "\x00" * 200 + "X" * 60 + " hello"
    page.insert_text(fitz.Point(50, 100), garbage)
    return doc.tobytes()


class TestDocumentAnalyzer:
    def test_clean_text_pipeline(self, clean_text_pdf: bytes) -> None:
        report = DocumentAnalyzer.from_bytes(clean_text_pdf)
        assert isinstance(report, DiagnosticReport)
        assert report.has_native_text is True
        assert report.page_count == 1
        assert report.is_encrypted is False
        assert report.text_quality_score > 0.9
        assert report.recommended_pipeline == PipelineType.NATIVE
        assert report.estimated_scanned is False

    def test_scanned_pipeline(self, scanned_pdf: bytes) -> None:
        report = DocumentAnalyzer.from_bytes(scanned_pdf)
        assert report.has_native_text is False
        assert report.text_quality_score == 0.0
        assert report.recommended_pipeline == PipelineType.OCR
        assert report.image_count > 0

    def test_rotated_pages(self, rotated_pdf: bytes) -> None:
        report = DocumentAnalyzer.from_bytes(rotated_pdf)
        assert 2 in report.rotated_pages
        assert 1 not in report.rotated_pages
        assert 3 not in report.rotated_pages

    def test_image_count(self, multi_image_pdf: bytes) -> None:
        report = DocumentAnalyzer.from_bytes(multi_image_pdf)
        assert report.image_count == 4

    def test_garbage_text_low_quality(self, garbage_text_pdf: bytes) -> None:
        report = DocumentAnalyzer.from_bytes(garbage_text_pdf)
        assert report.has_native_text is True
        assert report.text_quality_score < 0.5

    def test_from_bytes_returns_report(self, clean_text_pdf: bytes) -> None:
        report = DocumentAnalyzer.from_bytes(clean_text_pdf)
        assert isinstance(report, DiagnosticReport)
        assert report.file_path == ""

    def test_report_is_frozen(self, clean_text_pdf: bytes) -> None:
        report = DocumentAnalyzer.from_bytes(clean_text_pdf)
        with pytest.raises((TypeError, ValueError)):
            report.page_count = 99  # type: ignore[misc]

    def test_no_text_quality(self) -> None:
        assert DocumentAnalyzer._score_text_quality("") == 0.0

    def test_perfect_text_quality(self) -> None:
        text = "Hello world. This is a normal sentence with good quality text."
        score = DocumentAnalyzer._score_text_quality(text)
        assert score > 0.9

    def test_replacement_char_penalty(self) -> None:
        text = "\ufffd" * 50
        score = DocumentAnalyzer._score_text_quality(text)
        assert score < 0.5

    def test_estimate_scanned_high_images(self) -> None:
        assert DocumentAnalyzer._estimate_scanned(1, 5, 0.0) is True

    def test_estimate_scanned_low_quality(self) -> None:
        assert DocumentAnalyzer._estimate_scanned(1, 1, 0.1) is True

    def test_estimate_not_scanned(self) -> None:
        assert DocumentAnalyzer._estimate_scanned(1, 0, 0.9) is False

    def test_recommend_ocr_no_text(self) -> None:
        assert DocumentAnalyzer._recommend_pipeline(False, 0.0, False) == PipelineType.OCR

    def test_recommend_ocr_scanned(self) -> None:
        assert DocumentAnalyzer._recommend_pipeline(True, 0.9, True) == PipelineType.OCR

    def test_recommend_ocr_low_quality(self) -> None:
        assert DocumentAnalyzer._recommend_pipeline(True, 0.1, False) == PipelineType.OCR

    def test_recommend_hybrid(self) -> None:
        assert DocumentAnalyzer._recommend_pipeline(True, 0.5, False) == PipelineType.HYBRID

    def test_recommend_native(self) -> None:
        assert DocumentAnalyzer._recommend_pipeline(True, 0.9, False) == PipelineType.NATIVE

    def test_estimated_scanned_with_real_scanned(self, scanned_pdf: bytes) -> None:
        report = DocumentAnalyzer.from_bytes(scanned_pdf)
        assert report.estimated_scanned is True

    def test_recommended_pipeline_consistency(self, clean_text_pdf: bytes) -> None:
        report = DocumentAnalyzer.from_bytes(clean_text_pdf)
        assert report.recommended_pipeline in (
            PipelineType.NATIVE, PipelineType.OCR, PipelineType.HYBRID,
        )

    def test_file_path_in_report(self) -> None:
        import tempfile
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(fitz.Point(50, 100), "test")
        path = str(tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name)
        doc.save(path)
        doc.close()
        try:
            report = DocumentAnalyzer(path).analyze()
            assert report.file_path != ""
            assert path in report.file_path
        finally:
            import os
            os.remove(path)
