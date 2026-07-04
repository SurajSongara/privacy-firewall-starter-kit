from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from privacy_firewall.models.blocks import Block


class Page(BaseModel):
    model_config = ConfigDict(frozen=True)

    page_number: int
    width: float
    height: float
    blocks: list[Block] = []

    @field_validator("page_number")
    @classmethod
    def page_number_must_be_positive(cls, v: int) -> int:
        if v < 1:
            msg = "page_number must be >= 1"
            raise ValueError(msg)
        return v

    @field_validator("width")
    @classmethod
    def width_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            msg = "width must be positive"
            raise ValueError(msg)
        return v

    @field_validator("height")
    @classmethod
    def height_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            msg = "height must be positive"
            raise ValueError(msg)
        return v


class Document(BaseModel):
    model_config = ConfigDict(frozen=True)

    pages: list[Page] = []
