"""Tests for the non-PDF → PDF converters."""

from pathlib import Path

import fitz
import pytest

from privacy_firewall.parsers.converters import (
    SUPPORTED_SUFFIXES,
    ConversionError,
    convert_to_pdf,
    is_supported,
    needs_conversion,
)


def _make_png(path: Path) -> None:
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 120, 80))
    pix.clear_with(200)
    pix.save(str(path))


class TestSupportChecks:
    def test_supported_suffixes(self) -> None:
        assert ".pdf" in SUPPORTED_SUFFIXES
        for ext in (".png", ".jpg", ".txt", ".md", ".docx"):
            assert ext in SUPPORTED_SUFFIXES

    def test_is_supported(self) -> None:
        assert is_supported("scan.PNG")
        assert is_supported("notes.txt")
        assert not is_supported("archive.zip")

    def test_needs_conversion(self) -> None:
        assert needs_conversion("photo.jpg")
        assert not needs_conversion("statement.pdf")
        assert not needs_conversion("archive.zip")


class TestTextConversion:
    def test_txt_produces_pdf_with_text_layer(self, tmp_path: Path) -> None:
        src = tmp_path / "notes.txt"
        src.write_text("Phone: 9876543210\nEmail: user@example.com", encoding="utf-8")
        dest = convert_to_pdf(src, tmp_path / "notes.txt.pdf")
        assert dest.exists()
        with fitz.open(dest) as doc:
            text = doc[0].get_text()
        assert "9876543210" in text
        assert "user@example.com" in text

    def test_markdown_is_rendered_as_text(self, tmp_path: Path) -> None:
        src = tmp_path / "readme.md"
        src.write_text("# Title\n\nPAN: ABCDE1234F", encoding="utf-8")
        dest = convert_to_pdf(src, tmp_path / "readme.md.pdf")
        with fitz.open(dest) as doc:
            assert "ABCDE1234F" in doc[0].get_text()

    def test_long_text_paginates(self, tmp_path: Path) -> None:
        src = tmp_path / "long.txt"
        src.write_text("\n".join(f"line {i}" for i in range(400)), encoding="utf-8")
        dest = convert_to_pdf(src, tmp_path / "long.txt.pdf")
        with fitz.open(dest) as doc:
            assert doc.page_count > 1
            assert "line 0" in doc[0].get_text()
            assert "line 399" in doc[-1].get_text()

    def test_long_lines_wrap_without_loss(self, tmp_path: Path) -> None:
        src = tmp_path / "wide.txt"
        src.write_text("word " * 200 + "END-MARKER", encoding="utf-8")
        dest = convert_to_pdf(src, tmp_path / "wide.txt.pdf")
        with fitz.open(dest) as doc:
            all_text = "".join(page.get_text() for page in doc)
        assert "END-MARKER" in all_text

    def test_empty_file_yields_one_blank_page(self, tmp_path: Path) -> None:
        src = tmp_path / "empty.txt"
        src.write_text("", encoding="utf-8")
        dest = convert_to_pdf(src, tmp_path / "empty.txt.pdf")
        with fitz.open(dest) as doc:
            assert doc.page_count == 1


class TestImageConversion:
    def test_png_becomes_single_page_pdf(self, tmp_path: Path) -> None:
        src = tmp_path / "scan.png"
        _make_png(src)
        dest = convert_to_pdf(src, tmp_path / "scan.png.pdf")
        with fitz.open(dest) as doc:
            assert doc.page_count == 1
            assert doc[0].get_images()

    def test_corrupt_image_raises(self, tmp_path: Path) -> None:
        src = tmp_path / "broken.png"
        src.write_bytes(b"not an image")
        with pytest.raises(ConversionError, match="could not read image"):
            convert_to_pdf(src, tmp_path / "broken.png.pdf")


class TestDocxConversion:
    def test_docx_text_is_extracted(self, tmp_path: Path) -> None:
        docx = pytest.importorskip("docx")
        src = tmp_path / "letter.docx"
        document = docx.Document()
        document.add_paragraph("Dear Sir, my PAN is ABCDE1234F.")
        table = document.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "Phone"
        table.rows[0].cells[1].text = "9876543210"
        document.save(str(src))
        dest = convert_to_pdf(src, tmp_path / "letter.docx.pdf")
        with fitz.open(dest) as doc:
            text = "".join(page.get_text() for page in doc)
        assert "ABCDE1234F" in text
        assert "9876543210" in text

    def test_invalid_docx_raises(self, tmp_path: Path) -> None:
        pytest.importorskip("docx")
        src = tmp_path / "fake.docx"
        src.write_bytes(b"not a zip archive")
        with pytest.raises(ConversionError, match="could not read DOCX"):
            convert_to_pdf(src, tmp_path / "fake.docx.pdf")


class TestConversionMechanics:
    def test_cached_result_is_reused(self, tmp_path: Path) -> None:
        src = tmp_path / "notes.txt"
        src.write_text("hello", encoding="utf-8")
        dest = convert_to_pdf(src, tmp_path / "notes.txt.pdf")
        first_mtime = dest.stat().st_mtime_ns
        convert_to_pdf(src, dest)
        assert dest.stat().st_mtime_ns == first_mtime

    def test_stale_cache_is_rebuilt(self, tmp_path: Path) -> None:
        import os

        src = tmp_path / "notes.txt"
        src.write_text("old", encoding="utf-8")
        dest = convert_to_pdf(src, tmp_path / "notes.txt.pdf")
        # Make the source strictly newer than the converted file.
        os.utime(dest, (dest.stat().st_atime, src.stat().st_mtime - 10))
        src.write_text("new content", encoding="utf-8")
        convert_to_pdf(src, dest)
        with fitz.open(dest) as doc:
            assert "new content" in doc[0].get_text()

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConversionError, match="not found"):
            convert_to_pdf(tmp_path / "ghost.txt", tmp_path / "ghost.pdf")

    def test_unsupported_suffix_raises(self, tmp_path: Path) -> None:
        src = tmp_path / "data.zip"
        src.write_bytes(b"PK")
        with pytest.raises(ConversionError, match="unsupported file type"):
            convert_to_pdf(src, tmp_path / "data.pdf")
