from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from privacy_firewall.models.geometry import BoundingBox


class BlockType(StrEnum):
    """Supported content block types within a document page."""

    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"


class Block(BaseModel):
    """A content block extracted from a document page.

    Stores the block identifier, type, bounding geometry, page number,
    and detection confidence.
    """

    model_config = ConfigDict(frozen=True)

    block_id: str
    block_type: BlockType
    bbox: BoundingBox
    page_number: int
    confidence: float

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        """Validate that confidence is between 0.0 and 1.0 (inclusive)."""
        if not 0.0 <= v <= 1.0:
            msg = "confidence must be between 0 and 1"
            raise ValueError(msg)
        return v

    @field_validator("page_number")
    @classmethod
    def page_number_must_be_positive(cls, v: int) -> int:
        """Validate that page_number is >= 1."""
        if v < 1:
            msg = "page_number must be >= 1"
            raise ValueError(msg)
        return v


class TextBlock(Block):
    """A block containing extracted text content."""

    model_config = ConfigDict(frozen=True)

    block_type: Literal[BlockType.TEXT] = BlockType.TEXT
    text: str


class ImageBlock(Block):
    """A block containing image data with an optional MIME type."""

    model_config = ConfigDict(frozen=True)

    block_type: Literal[BlockType.IMAGE] = BlockType.IMAGE
    image_data: bytes | None = None
    mime_type: str | None = None


class TableBlock(Block):
    """A block representing tabular content as a list of string rows."""

    model_config = ConfigDict(frozen=True)

    block_type: Literal[BlockType.TABLE] = BlockType.TABLE
    rows: list[list[str]] = []
