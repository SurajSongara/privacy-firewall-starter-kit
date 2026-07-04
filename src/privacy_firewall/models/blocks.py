from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from privacy_firewall.models.geometry import BoundingBox


class BlockType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"


class Block(BaseModel, frozen=True):
    block_id: str
    block_type: BlockType
    bbox: BoundingBox
    page_number: int
    confidence: float

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            msg = "confidence must be between 0 and 1"
            raise ValueError(msg)
        return v

    @field_validator("page_number")
    @classmethod
    def page_number_must_be_positive(cls, v: int) -> int:
        if v < 1:
            msg = "page_number must be >= 1"
            raise ValueError(msg)
        return v


class TextBlock(Block):  # type: ignore[misc]
    model_config = ConfigDict(frozen=True)
    block_type: Literal[BlockType.TEXT] = BlockType.TEXT
    text: str


class ImageBlock(Block):  # type: ignore[misc]
    model_config = ConfigDict(frozen=True)
    block_type: Literal[BlockType.IMAGE] = BlockType.IMAGE
    image_data: bytes | None = None
    mime_type: str | None = None


class TableBlock(Block):  # type: ignore[misc]
    model_config = ConfigDict(frozen=True)
    block_type: Literal[BlockType.TABLE] = BlockType.TABLE
    rows: list[list[str]] = []
