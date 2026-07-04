"""Data models for layout analysis results."""
from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field

from privacy_firewall.models.blocks import Block
from privacy_firewall.models.geometry import BoundingBox


class LayoutElementType(enum.StrEnum):
    """Types of layout elements that can be identified on a page."""

    HEADER = "header"
    """Content at the top of a page (running header, title)."""

    FOOTER = "footer"
    """Content at the bottom of a page (running footer)."""

    PAGE_NUMBER = "page_number"
    """A page number, typically in the footer region."""

    PARAGRAPH = "paragraph"
    """A contiguous block of body text."""

    TABLE = "table"
    """Tabular content."""

    IMAGE = "image"
    """An image / figure."""

    OTHER = "other"
    """Unclassified content."""


class LayoutElement(BaseModel):
    """A single layout element identified on a page.

    Attributes:
        type: The element type.
        bbox: The bounding box encompassing all constituent blocks.
        blocks: The underlying document blocks that form this element.
        text: Concatenated text of all text blocks in this element.
        reading_order: Position in the page's reading order (0-based).
    """

    model_config = ConfigDict(frozen=True)

    type: LayoutElementType
    bbox: BoundingBox
    blocks: list[Block] = Field(default_factory=list)
    text: str = ""
    reading_order: int = 0


class LayoutAnalysis(BaseModel):
    """Layout analysis results for a single page.

    Attributes:
        page_number: 1-based page number.
        width: Page width.
        height: Page height.
        elements: Identified layout elements, ordered by reading order.
    """

    model_config = ConfigDict(frozen=True)

    page_number: int
    width: float
    height: float
    elements: list[LayoutElement] = Field(default_factory=list)
