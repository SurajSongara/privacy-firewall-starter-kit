from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from privacy_firewall.models.geometry import BoundingBox, Span


class Detection(BaseModel):
    model_config = ConfigDict(frozen=True)

    detector_name: str
    detection_type: str
    text: str
    span: Span
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
