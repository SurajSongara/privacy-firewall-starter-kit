from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from privacy_firewall.models.geometry import BoundingBox, Span


class Detection(BaseModel):
    """A single PII or sensitive-content detection result.

    Captures the detector that produced the match, the matched text,
    its character span and bounding box within the page, and the
    confidence score.
    """

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
        """Validate that confidence is between 0.0 and 1.0 (inclusive)."""
        if not 0.0 <= v <= 1.0:
            msg = "confidence must be between 0 and 1"
            raise ValueError(msg)
        return v
