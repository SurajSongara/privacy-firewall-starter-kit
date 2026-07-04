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

    def test_render_bytes_black_bar(self) -> None:
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
            page = doc[0]
            paths = page.get_drawings()
            assert len(paths) >= 1
            black_fills = [
                p for p in paths
                if p.get("fill") is not None
                and all(c == 0.0 for c in p["fill"][:3])
            ]
            assert len(black_fills) >= 1

    def test_render_bytes_highlight(self) -> None:
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
            assert len(paths) >= 1

    def test_render_bytes_highlight_uses_yellow(self) -> None:
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
                p for p in paths
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
            page0_paths = doc[0].get_drawings()
            page1_paths = doc[1].get_drawings()
            assert len(page0_paths) >= 1
            assert len(page1_paths) >= 1

    def test_no_redactions_produces_identical_copy(self) -> None:
        data = _make_simple_pdf()
        plan = RedactionPlan()
        result = PDFRenderer.render_bytes(data, plan)
        with fitz.open(stream=data, filetype="pdf") as orig:
            with fitz.open(stream=result, filetype="pdf") as rendered:
                assert len(rendered) == len(orig)
                for i in range(len(orig)):
                    assert rendered[i].rect == orig[i].rect
