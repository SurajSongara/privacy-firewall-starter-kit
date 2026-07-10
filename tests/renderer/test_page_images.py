from pathlib import Path

import fitz
import pytest

from privacy_firewall.models.geometry import BoundingBox
from privacy_firewall.renderer.page_images import (
    bbox_to_pixels,
    page_count,
    render_page_image,
)


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    path = tmp_path / "doc.pdf"
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    doc.new_page(width=612, height=792)
    doc.save(str(path))
    doc.close()
    return path


class TestPageImages:
    def test_page_count(self, pdf: Path) -> None:
        assert page_count(pdf) == 2

    def test_render_dimensions_at_144_dpi(self, pdf: Path) -> None:
        image = render_page_image(pdf, 1, dpi=144)
        assert image.scale == 2.0
        assert image.width == 1224
        assert image.height == 1584
        assert image.page_number == 1

    def test_png_magic_bytes(self, pdf: Path) -> None:
        image = render_page_image(pdf, 1)
        assert image.png_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_page_out_of_range(self, pdf: Path) -> None:
        with pytest.raises(ValueError, match="out of range"):
            render_page_image(pdf, 3)
        with pytest.raises(ValueError, match="out of range"):
            render_page_image(pdf, 0)

    def test_bbox_transform(self) -> None:
        bbox = BoundingBox(x0=10.0, y0=20.0, x1=110.0, y1=40.0)
        assert bbox_to_pixels(bbox, 2.0) == (20.0, 40.0, 220.0, 80.0)

    def test_bbox_transform_round_trip(self, pdf: Path) -> None:
        image = render_page_image(pdf, 1, dpi=96)
        bbox = BoundingBox(x0=50.0, y0=100.0, x1=200.0, y1=120.0)
        x0, y0, x1, y1 = bbox_to_pixels(bbox, image.scale)
        assert (x0 / image.scale, y0 / image.scale) == pytest.approx((bbox.x0, bbox.y0))
        assert (x1 / image.scale, y1 / image.scale) == pytest.approx((bbox.x1, bbox.y1))
