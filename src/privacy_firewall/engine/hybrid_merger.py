"""Hybrid merge of native text extraction and OCR results."""
from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict

from privacy_firewall.models.blocks import Block, TextBlock
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox


class BlockProvenance(enum.StrEnum):
    """Indicates the source of a block in a merged document."""

    NATIVE = "native"
    """Block originated from native PDF text extraction."""

    OCR = "ocr"
    """Block originated from OCR processing."""


class MergeResult(BaseModel):
    """Result of merging native and OCR documents.

    Attributes:
        document: The merged document with deduplicated blocks.
        provenance: Mapping from ``block_id`` to ``BlockProvenance``.
    """

    model_config = ConfigDict(frozen=True)

    document: Document
    provenance: dict[str, BlockProvenance] = {}


class HybridMerger:
    """Merges native text extraction with OCR results.

    Strategy (per page):
    1. Keep all native text blocks as-is (provenance = NATIVE).
    2. Add OCR text blocks whose bounding boxes do **not** significantly
       overlap with any existing native block (provenance = OCR).
    3. Blocks are ordered: native blocks first, then OCR fill-ins.
    """

    OVERLAP_THRESHOLD = 0.5
    """If the IoU-like overlap ratio exceeds this, the OCR block is skipped."""

    @classmethod
    def merge(cls, native: Document, ocr: Document) -> MergeResult:
        """Merge a native-parsed document with an OCR document.

        Args:
            native: Document produced by the native PDF parser.
            ocr: Document produced by an OCR provider.

        Returns:
            A ``MergeResult`` with the merged document and provenance map.
        """
        merged_pages: list[Page] = []
        provenance: dict[str, BlockProvenance] = {}
        max_pages = max(len(native.pages), len(ocr.pages))

        for page_idx in range(max_pages):
            native_page = native.pages[page_idx] if page_idx < len(native.pages) else None
            ocr_page = ocr.pages[page_idx] if page_idx < len(ocr.pages) else None

            merged, prov = cls._merge_page(native_page, ocr_page, page_idx + 1)
            merged_pages.append(merged)
            provenance.update(prov)

        return MergeResult(
            document=Document(pages=merged_pages),
            provenance=provenance,
        )

    @classmethod
    def _merge_page(
        cls,
        native_page: Page | None,
        ocr_page: Page | None,
        page_number: int,
    ) -> tuple[Page, dict[str, BlockProvenance]]:
        """Merge a single page from native and OCR sources.

        Args:
            native_page: The native-extracted page, or ``None``.
            ocr_page: The OCR-extracted page, or ``None``.
            page_number: 1-based page number for fallback page creation.

        Returns:
            A tuple of (merged Page, provenance mapping for this page).
        """
        provenance: dict[str, BlockProvenance] = {}
        merged_blocks: list[Block] = []

        native_blocks: list[Block] = []
        ocr_blocks: list[TextBlock] = []

        if native_page is not None:
            native_blocks = native_page.blocks
            width = native_page.width
            height = native_page.height
        elif ocr_page is not None:
            width = ocr_page.width
            height = ocr_page.height
        else:
            width = 595.0
            height = 842.0

        if ocr_page is not None:
            ocr_blocks = [b for b in ocr_page.blocks if isinstance(b, TextBlock)]

        # Keep all native blocks
        for block in native_blocks:
            merged_blocks.append(block)
            provenance[block.block_id] = BlockProvenance.NATIVE

        # Add OCR blocks that don't overlap significantly with native blocks
        for ocr_block in ocr_blocks:
            if not cls._has_significant_overlap(ocr_block, native_blocks):
                merged_blocks.append(ocr_block)
                provenance[ocr_block.block_id] = BlockProvenance.OCR

        page = Page(
            page_number=page_number,
            width=width,
            height=height,
            blocks=merged_blocks,
        )
        return page, provenance

    @staticmethod
    def _has_significant_overlap(ocr_block: TextBlock, native_blocks: list[Block]) -> bool:
        """Check if an OCR block overlaps significantly with any native block.

        Args:
            ocr_block: The OCR text block.
            native_blocks: Native blocks to check against.

        Returns:
            ``True`` if the OCR block overlaps above the threshold.
        """
        ocr_bbox = ocr_block.bbox
        for native_block in native_blocks:
            if not isinstance(native_block, TextBlock):
                continue
            ratio = HybridMerger._overlap_ratio(ocr_bbox, native_block.bbox)
            if ratio > HybridMerger.OVERLAP_THRESHOLD:
                return True
        return False

    @staticmethod
    def _overlap_ratio(a: BoundingBox, b: BoundingBox) -> float:
        """Compute the intersection-over-min-area ratio for two bboxes.

        Returns the area of the intersection divided by the area of the
        smaller bounding box (i.e. how much of the smaller box is covered
        by the overlap).

        Args:
            a: First bounding box.
            b: Second bounding box.

        Returns:
            A float in ``[0.0, 1.0]``.
        """
        ix0 = max(a.x0, b.x0)
        iy0 = max(a.y0, b.y0)
        ix1 = min(a.x1, b.x1)
        iy1 = min(a.y1, b.y1)

        if ix0 >= ix1 or iy0 >= iy1:
            return 0.0

        intersection = (ix1 - ix0) * (iy1 - iy0)
        area_b = (b.x1 - b.x0) * (b.y1 - b.y0)
        if area_b <= 0:
            return 0.0
        return intersection / area_b
