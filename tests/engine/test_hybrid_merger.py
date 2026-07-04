"""Tests for the HybridMerger."""
from __future__ import annotations

import pytest

from privacy_firewall.engine.hybrid_merger import BlockProvenance, HybridMerger, MergeResult
from privacy_firewall.models.blocks import ImageBlock, TextBlock
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox


def _make_text_block(
    block_id: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    text: str,
    confidence: float = 1.0,
) -> TextBlock:
    return TextBlock(
        block_id=block_id,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
        page_number=1,
        confidence=confidence,
        text=text,
    )


class TestHybridMerger:
    def test_merge_result_is_frozen(self) -> None:
        r = MergeResult(document=Document())
        with pytest.raises((TypeError, ValueError)):
            r.document = Document()  # type: ignore[misc]

    def test_provenance_empty_by_default(self) -> None:
        r = MergeResult(document=Document())
        assert r.provenance == {}

    def test_both_empty(self) -> None:
        result = HybridMerger.merge(Document(), Document())
        assert len(result.document.pages) == 0
        assert result.provenance == {}

    def test_only_native(self) -> None:
        native = Document(
            pages=[
                Page(
                    page_number=1, width=600, height=800,
                    blocks=[
                        _make_text_block("n1", 10, 10, 100, 30, "Hello native"),
                    ],
                ),
            ],
        )
        result = HybridMerger.merge(native, Document())
        assert len(result.document.pages) == 1
        assert len(result.document.pages[0].blocks) == 1
        assert result.provenance["n1"] == BlockProvenance.NATIVE

    def test_only_ocr(self) -> None:
        ocr = Document(
            pages=[
                Page(
                    page_number=1, width=600, height=800,
                    blocks=[
                        _make_text_block("o1", 10, 10, 100, 30, "Hello OCR", confidence=0.9),
                    ],
                ),
            ],
        )
        result = HybridMerger.merge(Document(), ocr)
        assert len(result.document.pages) == 1
        assert len(result.document.pages[0].blocks) == 1
        assert result.provenance["o1"] == BlockProvenance.OCR

    def test_non_overlapping_blocks_combined(self) -> None:
        native = Document(
            pages=[
                Page(
                    page_number=1, width=600, height=800,
                    blocks=[
                        _make_text_block("n1", 10, 10, 100, 30, "Top"),
                    ],
                ),
            ],
        )
        ocr = Document(
            pages=[
                Page(
                    page_number=1, width=600, height=800,
                    blocks=[
                        _make_text_block("o1", 10, 100, 100, 130, "Bottom", confidence=0.9),
                    ],
                ),
            ],
        )
        result = HybridMerger.merge(native, ocr)
        assert len(result.document.pages[0].blocks) == 2
        assert result.provenance["n1"] == BlockProvenance.NATIVE
        assert result.provenance["o1"] == BlockProvenance.OCR

    def test_overlapping_ocr_block_skipped(self) -> None:
        native = Document(
            pages=[
                Page(
                    page_number=1, width=600, height=800,
                    blocks=[
                        _make_text_block("n1", 10, 10, 200, 50, "Native covers area"),
                    ],
                ),
            ],
        )
        ocr = Document(
            pages=[
                Page(
                    page_number=1, width=600, height=800,
                    blocks=[
                        _make_text_block(
                            "o1", 20, 15, 180, 45, "OCR within native", confidence=0.9,
                        ),
                    ],
                ),
            ],
        )
        result = HybridMerger.merge(native, ocr)
        block_ids = [b.block_id for b in result.document.pages[0].blocks]
        assert "n1" in block_ids
        assert "o1" not in block_ids

    def test_non_text_blocks_preserved(self) -> None:
        native = Document(
            pages=[
                Page(
                    page_number=1, width=600, height=800,
                    blocks=[
                        ImageBlock(
                            block_id="img1",
                            bbox=BoundingBox(x0=0, y0=0, x1=50, y1=50),
                            page_number=1,
                            confidence=1.0,
                        ),
                    ],
                ),
            ],
        )
        result = HybridMerger.merge(native, Document())
        blocks = result.document.pages[0].blocks
        assert len(blocks) == 1
        assert isinstance(blocks[0], ImageBlock)
        assert result.provenance["img1"] == BlockProvenance.NATIVE

    def test_different_page_counts(self) -> None:
        native = Document(
            pages=[
                Page(page_number=1, width=600, height=800, blocks=[
                    _make_text_block("n1", 10, 10, 100, 30, "Page 1 native"),
                ]),
                Page(page_number=2, width=600, height=800, blocks=[
                    _make_text_block("n2", 10, 10, 100, 30, "Page 2 native"),
                ]),
            ],
        )
        ocr = Document(
            pages=[
                Page(page_number=1, width=600, height=800, blocks=[
                    _make_text_block("o1", 10, 100, 100, 130, "Page 1 OCR", confidence=0.9),
                ]),
            ],
        )
        result = HybridMerger.merge(native, ocr)
        assert len(result.document.pages) == 2
        assert len(result.document.pages[0].blocks) == 2  # native + OCR
        assert len(result.document.pages[1].blocks) == 1  # native only

    def test_overlap_ratio_identical(self) -> None:
        a = BoundingBox(x0=0, y0=0, x1=100, y1=100)
        b = BoundingBox(x0=0, y0=0, x1=100, y1=100)
        assert HybridMerger._overlap_ratio(a, b) == 1.0

    def test_overlap_ratio_none(self) -> None:
        a = BoundingBox(x0=0, y0=0, x1=10, y1=10)
        b = BoundingBox(x0=20, y0=20, x1=30, y1=30)
        assert HybridMerger._overlap_ratio(a, b) == 0.0

    def test_overlap_ratio_partial(self) -> None:
        a = BoundingBox(x0=0, y0=0, x1=100, y1=100)
        b = BoundingBox(x0=50, y0=0, x1=150, y1=100)
        ratio = HybridMerger._overlap_ratio(a, b)
        assert 0.0 < ratio < 1.0

    def test_overlap_below_threshold_kept(self) -> None:
        native = Document(
            pages=[
                Page(
                    page_number=1, width=600, height=800,
                    blocks=[
                        _make_text_block("n1", 0, 0, 100, 100, "Native block"),
                    ],
                ),
            ],
        )
        # An OCR block with minimal overlap
        ocr = Document(
            pages=[
                Page(
                    page_number=1, width=600, height=800,
                    blocks=[
                        _make_text_block(
                            "o1", 100, 100, 200, 200, "OCR barely touching", confidence=0.9,
                        ),
                    ],
                ),
            ],
        )
        result = HybridMerger.merge(native, ocr)
        block_ids = [b.block_id for b in result.document.pages[0].blocks]
        assert "o1" in block_ids
