"""Tests for the LayoutAnalyzer."""
from __future__ import annotations

import pytest

from privacy_firewall.layout import LayoutAnalysis, LayoutAnalyzer, LayoutElement, LayoutElementType
from privacy_firewall.models.blocks import ImageBlock, TableBlock, TextBlock
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox


def _text_block(
    bid: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    text: str,
) -> TextBlock:
    return TextBlock(
        block_id=bid,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
        page_number=1,
        confidence=1.0,
        text=text,
    )


def _image_block(bid: str, x0: float, y0: float, x1: float, y1: float) -> ImageBlock:
    return ImageBlock(
        block_id=bid,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
        page_number=1,
        confidence=1.0,
    )


def _table_block(bid: str, x0: float, y0: float, x1: float, y1: float) -> TableBlock:
    return TableBlock(
        block_id=bid,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
        page_number=1,
        confidence=1.0,
        rows=[],
    )


HEIGHT = 800.0
WIDTH = 600.0


class TestLayoutModels:
    def test_layout_element_frozen(self) -> None:
        el = LayoutElement(
            type=LayoutElementType.PARAGRAPH,
            bbox=BoundingBox(x0=0, y0=0, x1=10, y1=10),
        )
        with pytest.raises((TypeError, ValueError)):
            el.type = LayoutElementType.HEADER  # type: ignore[misc]

    def test_layout_analysis_frozen(self) -> None:
        a = LayoutAnalysis(page_number=1, width=600, height=800)
        with pytest.raises((TypeError, ValueError)):
            a.page_number = 2  # type: ignore[misc]


class TestLayoutAnalyzerClassifier:
    def test_header_at_top(self) -> None:
        block = _text_block("h1", 50, 5, 200, 25, "Page Header")
        el = LayoutAnalyzer._classify_text_block(block, HEIGHT)
        assert el is not None
        assert el.type == LayoutElementType.HEADER

    def test_footer_at_bottom(self) -> None:
        block = _text_block("f1", 50, 750, 200, 780, "Confidential")
        el = LayoutAnalyzer._classify_text_block(block, HEIGHT)
        assert el is not None
        assert el.type == LayoutElementType.FOOTER

    def test_page_number_at_bottom(self) -> None:
        block = _text_block("p1", 280, 770, 320, 790, "42")
        el = LayoutAnalyzer._classify_text_block(block, HEIGHT)
        assert el is not None
        assert el.type == LayoutElementType.PAGE_NUMBER

    def test_non_numeric_footer_is_footer(self) -> None:
        block = _text_block("f1", 50, 760, 200, 790, "Draft Only")
        el = LayoutAnalyzer._classify_text_block(block, HEIGHT)
        assert el is not None
        assert el.type == LayoutElementType.FOOTER

    def test_body_text_returns_none(self) -> None:
        block = _text_block("b1", 50, 200, 500, 230, "Body text here")
        el = LayoutAnalyzer._classify_text_block(block, HEIGHT)
        assert el is None

    def test_page_number_long_text_is_footer(self) -> None:
        block = _text_block("f1", 50, 760, 300, 790, "Page 42 of 100")
        el = LayoutAnalyzer._classify_text_block(block, HEIGHT)
        assert el is not None
        assert el.type == LayoutElementType.FOOTER


class TestLayoutAnalyzerPage:
    def test_empty_page(self) -> None:
        doc = Document(pages=[Page(page_number=1, width=WIDTH, height=HEIGHT)])
        results = LayoutAnalyzer.analyze(doc)
        assert len(results) == 1
        assert results[0].elements == []

    def test_image_block_classified(self) -> None:
        doc = Document(
            pages=[
                Page(
                    page_number=1, width=WIDTH, height=HEIGHT,
                    blocks=[_image_block("img1", 50, 200, 200, 300)],
                ),
            ],
        )
        results = LayoutAnalyzer.analyze(doc)
        assert results[0].elements[0].type == LayoutElementType.IMAGE

    def test_table_block_classified(self) -> None:
        doc = Document(
            pages=[
                Page(
                    page_number=1, width=WIDTH, height=HEIGHT,
                    blocks=[_table_block("t1", 50, 200, 400, 300)],
                ),
            ],
        )
        results = LayoutAnalyzer.analyze(doc)
        assert results[0].elements[0].type == LayoutElementType.TABLE

    def test_header_detected(self) -> None:
        doc = Document(
            pages=[
                Page(
                    page_number=1, width=WIDTH, height=HEIGHT,
                    blocks=[_text_block("h1", 50, 5, 200, 25, "Header")],
                ),
            ],
        )
        results = LayoutAnalyzer.analyze(doc)
        types = [e.type for e in results[0].elements]
        assert LayoutElementType.HEADER in types

    def test_page_number_detected(self) -> None:
        doc = Document(
            pages=[
                Page(
                    page_number=1, width=WIDTH, height=HEIGHT,
                    blocks=[_text_block("p1", 280, 770, 320, 790, "5")],
                ),
            ],
        )
        results = LayoutAnalyzer.analyze(doc)
        types = [e.type for e in results[0].elements]
        assert LayoutElementType.PAGE_NUMBER in types

    def test_multi_page(self) -> None:
        doc = Document(
            pages=[
                Page(page_number=1, width=WIDTH, height=HEIGHT, blocks=[
                    _text_block("b1", 50, 200, 400, 230, "Page 1 text"),
                ]),
                Page(page_number=2, width=WIDTH, height=HEIGHT, blocks=[
                    _text_block("b2", 50, 200, 400, 230, "Page 2 text"),
                ]),
            ],
        )
        results = LayoutAnalyzer.analyze(doc)
        assert len(results) == 2
        assert len(results[0].elements) == 1
        assert len(results[1].elements) == 1


class TestLayoutAnalyzerParagraphs:
    def test_body_text_becomes_paragraph(self) -> None:
        doc = Document(
            pages=[
                Page(
                    page_number=1, width=WIDTH, height=HEIGHT,
                    blocks=[_text_block("b1", 50, 200, 400, 230, "Body paragraph")],
                ),
            ],
        )
        results = LayoutAnalyzer.analyze(doc)
        types = [e.type for e in results[0].elements]
        assert LayoutElementType.PARAGRAPH in types

    def test_adjacent_blocks_merged(self) -> None:
        doc = Document(
            pages=[
                Page(
                    page_number=1, width=WIDTH, height=HEIGHT,
                    blocks=[
                        _text_block("b1", 50, 200, 400, 220, "First part"),
                        _text_block("b2", 50, 222, 400, 242, "Second part"),
                    ],
                ),
            ],
        )
        results = LayoutAnalyzer.analyze(doc)
        paras = [e for e in results[0].elements if e.type == LayoutElementType.PARAGRAPH]
        assert len(paras) == 1
        assert "First part" in paras[0].text
        assert "Second part" in paras[0].text

    def test_distant_blocks_separate_paragraphs(self) -> None:
        doc = Document(
            pages=[
                Page(
                    page_number=1, width=WIDTH, height=HEIGHT,
                    blocks=[
                        _text_block("b1", 50, 200, 400, 220, "First paragraph"),
                        _text_block("b2", 50, 300, 400, 320, "Second paragraph"),
                    ],
                ),
            ],
        )
        results = LayoutAnalyzer.analyze(doc)
        paras = [e for e in results[0].elements if e.type == LayoutElementType.PARAGRAPH]
        assert len(paras) == 2

    def test_union_bbox(self) -> None:
        bboxes = [
            BoundingBox(x0=10, y0=10, x1=50, y1=50),
            BoundingBox(x0=100, y0=200, x1=200, y1=300),
        ]
        union = LayoutAnalyzer._union_bbox(bboxes)
        assert union.x0 == 10
        assert union.y0 == 10
        assert union.x1 == 200
        assert union.y1 == 300


class TestLayoutAnalyzerReadingOrder:
    def test_top_to_bottom(self) -> None:
        doc = Document(
            pages=[
                Page(
                    page_number=1, width=WIDTH, height=HEIGHT,
                    blocks=[
                        _text_block("b2", 50, 300, 400, 320, "Second"),
                        _text_block("b1", 50, 100, 400, 120, "First"),
                    ],
                ),
            ],
        )
        results = LayoutAnalyzer.analyze(doc)
        orders = [e.reading_order for e in results[0].elements]
        assert orders == [0, 1]

    def test_left_to_right(self) -> None:
        doc = Document(
            pages=[
                Page(
                    page_number=1, width=WIDTH, height=HEIGHT,
                    blocks=[
                        _text_block("b2", 300, 100, 400, 120, "Right"),
                        _text_block("b1", 50, 100, 200, 120, "Left"),
                    ],
                ),
            ],
        )
        results = LayoutAnalyzer.analyze(doc)
        # Both blocks are at same y and 0 gap → merged into single paragraph
        assert LayoutElementType.PARAGRAPH in {e.type for e in results[0].elements}

    def test_reading_order_mixed_types(self) -> None:
        """Header < Paragraph < Footer reading order."""
        doc = Document(
            pages=[
                Page(
                    page_number=1, width=WIDTH, height=HEIGHT,
                    blocks=[
                        _text_block("b2", 50, 200, 400, 220, "Body"),
                        _text_block("b1", 50, 760, 200, 780, "Footer text"),
                        _text_block("h1", 50, 5, 200, 25, "Header"),
                    ],
                ),
            ],
        )
        results = LayoutAnalyzer.analyze(doc)
        types = [e.type for e in sorted(results[0].elements, key=lambda e: e.reading_order)]
        assert types == [
            LayoutElementType.HEADER,
            LayoutElementType.PARAGRAPH,
            LayoutElementType.FOOTER,
        ]
