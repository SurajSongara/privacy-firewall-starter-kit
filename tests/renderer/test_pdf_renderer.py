"""Tests for the PDF renderer."""

from pathlib import Path

import fitz

from privacy_firewall.engine.redaction import Redaction, RedactionPlan, RedactionType
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.geometry import BoundingBox, Span
from privacy_firewall.renderer.pdf_renderer import PDFRenderer


def _make_simple_pdf() -> bytes:
    """Generate a one-page PDF with sample text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "My PAN is ABCDE1234F", fontsize=12)
    page.insert_text((50, 150), "Contact: user@example.com", fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def _make_two_page_pdf() -> bytes:
    """Generate a two-page PDF with sample text."""
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((50, 100), "Page one PAN: AAAAAB1111B", fontsize=12)
    page2 = doc.new_page()
    page2.insert_text((50, 100), "Page two email: user@test.com", fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def _detection(
    bbox: BoundingBox | None = None,
    page_number: int = 1,
) -> Detection:
    """Create a Detection fixture."""
    return Detection(
        detector_name="pan",
        detection_type="PAN",
        text="ABCDE1234F",
        span=Span(start=10, end=20),
        bbox=bbox or BoundingBox(x0=45.0, y0=88.0, x1=155.0, y1=112.0),
        page_number=page_number,
        confidence=0.95,
    )


class TestPDFRenderer:
    """Verify that PDFRenderer produces correctly redacted PDF copies."""

    def setup_method(self) -> None:
        self.renderer = PDFRenderer()

    def test_render_bytes_output_differs_from_input(self) -> None:
        data = _make_simple_pdf()
        det = _detection()
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det,
                    redaction_type=RedactionType.BLACK_BAR,
                    page_number=1,
                    span=det.span,
                    bbox=det.bbox,
                )
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        assert result != data
        assert len(result) > 0

    def test_render_bytes_page_count_preserved(self) -> None:
        data = _make_two_page_pdf()
        det = _detection(page_number=1)
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det,
                    redaction_type=RedactionType.BLACK_BAR,
                    page_number=1,
                    span=det.span,
                    bbox=det.bbox,
                )
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=result, filetype="pdf") as doc:
            assert len(doc) == 2

    def test_black_bar_removes_text_content(self) -> None:
        """BLACK_BAR redaction should physically remove the text."""
        data = _make_simple_pdf()
        det = _detection()
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det,
                    redaction_type=RedactionType.BLACK_BAR,
                    page_number=1,
                    span=det.span,
                    bbox=det.bbox,
                )
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=result, filetype="pdf") as doc:
            page_text = doc[0].get_text()
        assert "ABCDE1234F" not in page_text, "Text should be removed, not just covered"

    def test_replace_removes_text_content(self) -> None:
        """REPLACE redaction should physically remove the text."""
        data = _make_simple_pdf()
        det = _detection()
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det,
                    redaction_type=RedactionType.REPLACE,
                    page_number=1,
                    span=det.span,
                    bbox=det.bbox,
                )
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=result, filetype="pdf") as doc:
            page_text = doc[0].get_text()
        assert "ABCDE1234F" not in page_text

    def test_replace_draws_stars_instead_of_black_bar(self) -> None:
        """REPLACE redaction should render the replacement text (stars)."""
        data = _make_simple_pdf()
        det = _detection()
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det,
                    redaction_type=RedactionType.REPLACE,
                    replacement_text="*****",
                    page_number=1,
                    span=det.span,
                    bbox=det.bbox,
                )
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=result, filetype="pdf") as doc:
            page_text = doc[0].get_text()
        assert "ABCDE1234F" not in page_text
        assert "*****" in page_text

    def test_replace_without_text_falls_back_to_stars(self) -> None:
        """A REPLACE redaction with no replacement_text still draws stars."""
        data = _make_simple_pdf()
        det = _detection()
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det,
                    redaction_type=RedactionType.REPLACE,
                    replacement_text=None,
                    page_number=1,
                    span=det.span,
                    bbox=det.bbox,
                )
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=result, filetype="pdf") as doc:
            page_text = doc[0].get_text()
        assert "*****" in page_text

    def test_replace_matches_original_font_size(self) -> None:
        """Replacement stars adopt the size of the text they replace."""
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 100), "PAN: ABCDE1234F", fontsize=8)
        data = doc.tobytes()
        doc.close()
        det = _detection(bbox=BoundingBox(x0=45.0, y0=90.0, x1=155.0, y1=104.0))
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det,
                    redaction_type=RedactionType.REPLACE,
                    replacement_text="**********",
                    page_number=1,
                    span=det.span,
                    bbox=det.bbox,
                )
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=result, filetype="pdf") as out:
            spans = [
                span
                for block in out[0].get_text("dict")["blocks"]
                if block.get("type") == 0
                for line in block["lines"]
                for span in line["spans"]
                if "*" in span["text"]
            ]
        assert spans, "replacement stars must be drawn"
        assert abs(spans[0]["size"] - 8) < 1.5

    def test_replace_preserves_text_color(self) -> None:
        """White text on a dark band stays white after replacement."""
        doc = fitz.open()
        page = doc.new_page()
        page.draw_rect(fitz.Rect(40, 80, 200, 115), color=None, fill=(0.2, 0.2, 0.5))
        page.insert_text((50, 100), "ABCDE1234F", fontsize=12, color=(1, 1, 1))
        data = doc.tobytes()
        doc.close()
        det = _detection(bbox=BoundingBox(x0=45.0, y0=88.0, x1=155.0, y1=104.0))
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det,
                    redaction_type=RedactionType.REPLACE,
                    replacement_text="**********",
                    page_number=1,
                    span=det.span,
                    bbox=det.bbox,
                )
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=result, filetype="pdf") as out:
            spans = [
                span
                for block in out[0].get_text("dict")["blocks"]
                if block.get("type") == 0
                for line in block["lines"]
                for span in line["spans"]
                if "*" in span["text"]
            ]
        assert spans, "replacement stars must be drawn"
        assert spans[0]["color"] == 0xFFFFFF  # white, like the original

    def test_base14_font_mapping(self) -> None:
        assert PDFRenderer._base14_for("Courier-Bold") == "cour"
        assert PDFRenderer._base14_for("JetBrainsMono-Regular") == "cour"
        assert PDFRenderer._base14_for("TimesNewRomanPSMT") == "tiro"
        assert PDFRenderer._base14_for("Helvetica") == "helv"
        assert PDFRenderer._base14_for("Arial-BoldMT") == "helv"
        assert PDFRenderer._base14_for("") == "helv"

    def test_highlight_preserves_text_content(self) -> None:
        """HIGHLIGHT should be visual-only and not remove text."""
        data = _make_simple_pdf()
        det = _detection()
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det,
                    redaction_type=RedactionType.HIGHLIGHT,
                    page_number=1,
                    span=det.span,
                    bbox=det.bbox,
                )
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=result, filetype="pdf") as doc:
            page_text = doc[0].get_text()
        assert "ABCDE1234F" in page_text

    def test_highlight_has_yellow_overlay(self) -> None:
        """HIGHLIGHT should add a yellow drawing."""
        data = _make_simple_pdf()
        det = _detection()
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det,
                    redaction_type=RedactionType.HIGHLIGHT,
                    page_number=1,
                    span=det.span,
                    bbox=det.bbox,
                )
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=result, filetype="pdf") as doc:
            page = doc[0]
            paths = page.get_drawings()
            yellow_fills = [
                p
                for p in paths
                if p.get("fill") is not None
                and p["fill"][0] == 1.0
                and p["fill"][1] == 1.0
                and p["fill"][2] == 0.0
            ]
            assert len(yellow_fills) >= 1

    def test_render_bytes_creates_output_file(self, tmp_path: Path) -> None:
        data = _make_simple_pdf()
        input_path = tmp_path / "input.pdf"
        output_path = tmp_path / "output.pdf"
        input_path.write_bytes(data)

        det = _detection()
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det,
                    redaction_type=RedactionType.BLACK_BAR,
                    page_number=1,
                    span=det.span,
                    bbox=det.bbox,
                )
            ]
        )
        result = self.renderer.render(input_path, output_path, plan)
        assert result == output_path.resolve()
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_original_pdf_unchanged(self, tmp_path: Path) -> None:
        data = _make_simple_pdf()
        input_path = tmp_path / "input.pdf"
        output_path = tmp_path / "output.pdf"
        input_path.write_bytes(data)

        det = _detection()
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det,
                    redaction_type=RedactionType.BLACK_BAR,
                    page_number=1,
                    span=det.span,
                    bbox=det.bbox,
                )
            ]
        )
        self.renderer.render(input_path, output_path, plan)
        assert input_path.read_bytes() == data

    def test_multi_page_redactions_on_correct_pages(self) -> None:
        data = _make_two_page_pdf()
        det1 = _detection(page_number=1)
        det2 = _detection(page_number=2)
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det1,
                    redaction_type=RedactionType.BLACK_BAR,
                    page_number=1,
                    span=det1.span,
                    bbox=det1.bbox,
                ),
                Redaction(
                    detection=det2,
                    redaction_type=RedactionType.BLACK_BAR,
                    page_number=2,
                    span=det2.span,
                    bbox=det2.bbox,
                ),
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=result, filetype="pdf") as doc:
            assert len(doc) == 2
            page0_text = doc[0].get_text()
            page1_text = doc[1].get_text()
            assert "AAAAAB1111B" not in page0_text
            assert "user@test.com" not in page1_text

    def test_no_redactions_produces_identical_copy(self) -> None:
        data = _make_simple_pdf()
        plan = RedactionPlan()
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=data, filetype="pdf") as orig:
            with fitz.open(stream=result, filetype="pdf") as rendered:
                assert len(rendered) == len(orig)
                for i in range(len(orig)):
                    assert rendered[i].rect == orig[i].rect

    def test_mixed_redaction_types(self) -> None:
        """Black-bar on page 1, highlight on page 2."""
        data = _make_two_page_pdf()
        det1 = _detection(page_number=1)
        det2 = _detection(page_number=2)
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=det1,
                    redaction_type=RedactionType.BLACK_BAR,
                    page_number=1,
                    span=det1.span,
                    bbox=det1.bbox,
                ),
                Redaction(
                    detection=det2,
                    redaction_type=RedactionType.HIGHLIGHT,
                    page_number=2,
                    span=det2.span,
                    bbox=det2.bbox,
                ),
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=result, filetype="pdf") as doc:
            assert len(doc) == 2
            page0_text = doc[0].get_text()
            page1_text = doc[1].get_text()
            assert "AAAAAB1111B" not in page0_text
            assert "user@test.com" in page1_text
