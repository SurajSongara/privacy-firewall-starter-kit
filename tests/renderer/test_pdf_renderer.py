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

    def test_replace_does_not_shift_surviving_line_text(self) -> None:
        """Kerned lines must not drift when part of them is redacted.

        MuPDF rewrites any text line a redaction touches and drops the
        original TJ kerning, shifting the surviving text sideways. The
        renderer removes affected lines whole and re-inserts survivors
        at their original positions, so positions must be identical.
        """
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 700), "placeholder", fontname="helv", fontsize=10)
        # Rewrite the content stream with an explicitly kerned TJ line.
        doc.update_stream(
            page.get_contents()[0],
            b"BT /helv 10 Tf 50 700 Td [(SECRET1234) -600 ( KEEPME) -600 ( TAIL)] TJ ET",
        )
        data = doc.tobytes()
        doc.close()

        def x_of(pdf: bytes, needle: str) -> float:
            with fitz.open(stream=pdf, filetype="pdf") as d:
                rects = d[0].search_for(needle)
            assert rects, f"{needle} not found"
            return rects[0].x0

        keep_before = x_of(data, "KEEPME")
        tail_before = x_of(data, "TAIL")

        det = _detection()
        det = det.model_copy(update={"text": "SECRET1234"})
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
        with fitz.open(stream=result, filetype="pdf") as d:
            text = d[0].get_text()
        assert "SECRET1234" not in text
        assert "KEEPME" in text
        assert "*" in text
        assert abs(x_of(result, "KEEPME") - keep_before) < 0.5
        assert abs(x_of(result, "TAIL") - tail_before) < 0.5

    def test_overlapping_detections_render_one_star_run(self) -> None:
        """Detector + manual entries covering the same text must not
        paint stars over stars — overlapping same-type rects merge."""
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 100), "Mail: user@example.com done", fontsize=12)
        email_rects = page.search_for("user@example.com")
        assert email_rects
        full = email_rects[0]
        data = doc.tobytes()
        doc.close()

        def email_det(x1: float) -> Detection:
            return Detection(
                detector_name="email",
                detection_type="EMAIL",
                text="user@example.com",
                span=Span(start=6, end=22),
                bbox=BoundingBox(x0=full.x0, y0=full.y0, x1=x1, y1=full.y1),
                page_number=1,
                confidence=0.9,
            )

        # Full-width detector bbox + a half-width manual bbox of the same text.
        half_x1 = full.x0 + (full.x1 - full.x0) / 2
        plan = RedactionPlan(
            redactions=[
                Redaction(
                    detection=email_det(full.x1),
                    redaction_type=RedactionType.REPLACE,
                    replacement_text="****************",
                    page_number=1,
                    bbox=email_det(full.x1).bbox,
                ),
                Redaction(
                    detection=email_det(half_x1),
                    redaction_type=RedactionType.REPLACE,
                    replacement_text="********",
                    page_number=1,
                    bbox=email_det(half_x1).bbox,
                ),
            ]
        )
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=result, filetype="pdf") as d:
            text = d[0].get_text()
            star_words = [w for w in text.split() if set(w) == {"*"}]
        assert "user@example.com" not in text
        assert "Mail:" in text and "done" in text
        assert len(star_words) == 1  # one clean star run, not two overlapping

    def test_merge_overlapping_jobs_keeps_disjoint_rects(self) -> None:
        a = fitz.Rect(0, 0, 10, 10)
        b = fitz.Rect(20, 0, 30, 10)  # disjoint
        c = fitz.Rect(5, 0, 25, 10)  # bridges both
        jobs = [
            (a, RedactionType.REPLACE, "***"),
            (b, RedactionType.REPLACE, "*****"),
            (c, RedactionType.REPLACE, "**********"),
        ]
        merged = PDFRenderer._merge_overlapping_jobs(jobs)
        assert len(merged) == 1  # c chains a and b into one union
        rect, rtype, replacement = merged[0]
        assert rect == fitz.Rect(0, 0, 30, 10)
        assert replacement == "**********"  # widest rect's replacement wins

        disjoint = PDFRenderer._merge_overlapping_jobs(jobs[:2])
        assert len(disjoint) == 2  # nothing merged without overlap

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
