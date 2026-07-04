from pydantic import BaseModel, ValidationInfo, field_validator


class BoundingBox(BaseModel, frozen=True):
    x0: float
    y0: float
    x1: float
    y1: float

    @field_validator("x1")
    @classmethod
    def x1_must_exceed_x0(cls, v: float, info: ValidationInfo) -> float:
        if "x0" in info.data and v <= info.data["x0"]:
            msg = "x1 must be greater than x0"
            raise ValueError(msg)
        return v

    @field_validator("y1")
    @classmethod
    def y1_must_exceed_y0(cls, v: float, info: ValidationInfo) -> float:
        if "y0" in info.data and v <= info.data["y0"]:
            msg = "y1 must be greater than y0"
            raise ValueError(msg)
        return v


class Span(BaseModel, frozen=True):
    start: int
    end: int

    @field_validator("end")
    @classmethod
    def end_must_exceed_start(cls, v: int, info: ValidationInfo) -> int:
        if "start" in info.data and v <= info.data["start"]:
            msg = "end must be greater than start"
            raise ValueError(msg)
        return v

    @field_validator("start")
    @classmethod
    def start_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            msg = "start must be non-negative"
            raise ValueError(msg)
        return v
