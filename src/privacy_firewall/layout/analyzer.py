"""Layout analysis — identifies structural elements in document pages."""
from __future__ import annotations

from privacy_firewall.layout.models import LayoutAnalysis, LayoutElement, LayoutElementType
from privacy_firewall.models.blocks import Block, ImageBlock, TableBlock, TextBlock
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import BoundingBox


class LayoutAnalyzer:
    """Analyses a parsed document and identifies layout elements.

    Heuristics are used to classify blocks into:
    - **Headers**: text blocks in the top 10 % of the page.
    - **Footers**: text blocks in the bottom 10 % of the page.
    - **Page numbers**: short numeric text in the footer region.
    - **Tables**: existing ``TableBlock`` items.
    - **Images**: existing ``ImageBlock`` items.
    - **Paragraphs**: remaining text blocks, merged when vertically adjacent.
    - **Other**: unclassified blocks.

    Reading order is determined top-to-bottom, left-to-right within
    overlapping y-ranges.
    """

    HEADER_MARGIN_RATIO = 0.10
    """Top ``HEADER_MARGIN_RATIO`` of page height is considered a header."""

    FOOTER_MARGIN_RATIO = 0.10
    """Bottom ``FOOTER_MARGIN_RATIO`` of page height is considered a footer."""

    PARAGRAPH_Y_GAP = 15.0
    """Vertical gap (pts) below which text blocks are merged into one paragraph."""

    PAGE_NUMBER_MAX_LENGTH = 10
    """Max characters allowed for a page-number candidate."""

    @classmethod
    def analyze(cls, document: Document) -> list[LayoutAnalysis]:
        """Analyse every page of a document and return layout results.

        Args:
            document: The parsed document.

        Returns:
            A list of ``LayoutAnalysis``, one per page.
        """
        return [
            cls._analyze_page(page.page_number, page.width, page.height, page.blocks)
            for page in document.pages
        ]

    @classmethod
    def _analyze_page(
        cls,
        page_number: int,
        width: float,
        height: float,
        blocks: list[Block],
    ) -> LayoutAnalysis:
        """Analyse a single page.

        Args:
            page_number: 1-based page number.
            width: Page width.
            height: Page height.
            blocks: Document blocks on this page.

        Returns:
            A ``LayoutAnalysis`` for the page.
        """
        elements: list[LayoutElement] = []
        remaining: list[TextBlock] = []

        for block in blocks:
            if isinstance(block, TableBlock):
                elements.append(cls._element(block, LayoutElementType.TABLE))
            elif isinstance(block, ImageBlock):
                elements.append(cls._element(block, LayoutElementType.IMAGE))
            elif isinstance(block, TextBlock):
                element = cls._classify_text_block(block, height)
                if element is not None:
                    elements.append(element)
                else:
                    remaining.append(block)

        # Merge remaining text blocks into paragraphs
        paragraphs = cls._merge_paragraphs(remaining)

        # Combine elements, sort by reading order
        all_elements = elements + paragraphs
        cls._assign_reading_order(all_elements)

        return LayoutAnalysis(
            page_number=page_number,
            width=width,
            height=height,
            elements=all_elements,
        )

    @classmethod
    def _classify_text_block(
        cls,
        block: TextBlock,
        page_height: float,
    ) -> LayoutElement | None:
        """Classify a text block as header, footer, page-number, or None.

        Args:
            block: The text block to classify.
            page_height: Total page height.

        Returns:
            A ``LayoutElement`` if the block matches a special type,
            or ``None`` if it should be considered body text.
        """
        y_center = (block.bbox.y0 + block.bbox.y1) / 2

        if y_center > page_height * (1 - cls.FOOTER_MARGIN_RATIO):
            text = block.text.strip()
            if text.isdigit() and len(text) <= cls.PAGE_NUMBER_MAX_LENGTH:
                return cls._element(block, LayoutElementType.PAGE_NUMBER)
            return cls._element(block, LayoutElementType.FOOTER)

        if y_center < page_height * cls.HEADER_MARGIN_RATIO:
            return cls._element(block, LayoutElementType.HEADER)

        return None

    @classmethod
    def _merge_paragraphs(cls, blocks: list[TextBlock]) -> list[LayoutElement]:
        """Merge vertically adjacent text blocks into paragraphs.

        Args:
            blocks: Text blocks to merge (already sorted top-to-bottom).

        Returns:
            A list of paragraph ``LayoutElement`` items.
        """
        if not blocks:
            return []

        sorted_blocks = sorted(blocks, key=lambda b: (b.bbox.y0, b.bbox.x0))
        merged: list[list[TextBlock]] = [[sorted_blocks[0]]]

        for block in sorted_blocks[1:]:
            prev = merged[-1][-1]
            gap = block.bbox.y0 - prev.bbox.y1
            if gap < cls.PARAGRAPH_Y_GAP:
                merged[-1].append(block)
            else:
                merged.append([block])

        paragraphs: list[LayoutElement] = []
        for group in merged:
            bbox = cls._union_bbox([b.bbox for b in group])
            text = " ".join(b.text for b in group)
            paragraphs.append(
                LayoutElement(
                    type=LayoutElementType.PARAGRAPH,
                    bbox=bbox,
                    blocks=list(group),
                    text=text,
                ),
            )

        return paragraphs

    @staticmethod
    def _assign_reading_order(elements: list[LayoutElement]) -> None:
        """Assign reading order: top-to-bottom, left-to-right.

        Args:
            elements: Layout elements to sort and assign in-place.
        """
        elements.sort(key=lambda e: (e.bbox.y0, e.bbox.x0))
        for i, el in enumerate(elements):
            elements[i] = LayoutElement(
                type=el.type,
                bbox=el.bbox,
                blocks=el.blocks,
                text=el.text,
                reading_order=i,
            )

    @staticmethod
    def _element(block: Block, el_type: LayoutElementType) -> LayoutElement:
        """Build a ``LayoutElement`` from a single block.

        Args:
            block: The source block.
            el_type: The layout element type.

        Returns:
            A ``LayoutElement`` wrapping the block.
        """
        text = block.text if isinstance(block, TextBlock) else ""
        return LayoutElement(
            type=el_type,
            bbox=block.bbox,
            blocks=[block],
            text=text,
            reading_order=0,
        )

    @staticmethod
    def _union_bbox(bboxes: list[BoundingBox]) -> BoundingBox:
        """Compute the union of multiple bounding boxes.

        Args:
            bboxes: List of bounding boxes.

        Returns:
            A single ``BoundingBox`` encompassing all inputs.
        """
        x0 = min(b.x0 for b in bboxes)
        y0 = min(b.y0 for b in bboxes)
        x1 = max(b.x1 for b in bboxes)
        y1 = max(b.y1 for b in bboxes)
        return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)
