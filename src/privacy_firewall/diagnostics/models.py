"""Data models for document diagnostics."""
from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field


class PipelineType(enum.StrEnum):
    """Recommended processing pipeline for a document."""

    NATIVE = "native"
    """Document has high-quality extractable text — use native parser."""

    OCR = "ocr"
    """Document is scanned or has very low text quality — use OCR."""

    HYBRID = "hybrid"
    """Mixed content — extract native text where possible, OCR the rest."""


class TextQualityReport(BaseModel):
    """Detailed breakdown of text quality heuristics.

    Attributes:
        overall_score: Aggregated quality score in ``[0.0, 1.0]``.
        printable_ratio: Fraction of characters that are printable.
        replace_penalty: Penalty factor for replacement characters.
        fragmentation_score: Score penalising many short (1-2 char) words.
        token_quality: Score penalising very long unbroken tokens.
        whitespace_ratio: Fraction of characters that are whitespace.
        reasons: Human-readable list of quality issues detected.
    """

    model_config = ConfigDict(frozen=True)

    overall_score: float = Field(ge=0.0, le=1.0)
    printable_ratio: float = Field(ge=0.0, le=1.0)
    replace_penalty: float = Field(ge=0.0, le=1.0)
    fragmentation_score: float = Field(ge=0.0, le=1.0)
    token_quality: float = Field(ge=0.0, le=1.0)
    whitespace_ratio: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = []


class DiagnosticReport(BaseModel):
    """Analysis results for a single PDF document.

    Attributes:
        file_path: Absolute path to the analysed file (empty for byte input).
        page_count: Number of pages in the document.
        image_count: Total number of embedded images across all pages.
        has_native_text: ``True`` if any page contains extractable text.
        is_encrypted: ``True`` if the document requires a password.
        rotated_pages: List of 1-based page numbers that are rotated.
        estimated_scanned: ``True`` if the document appears to be a scan.
        text_quality_report: Detailed text quality breakdown (``None`` when no text).
        recommended_pipeline: Which pipeline to use.
    """

    model_config = ConfigDict(frozen=True)

    file_path: str = ""
    page_count: int = 0
    image_count: int = 0
    has_native_text: bool = False
    is_encrypted: bool = False
    rotated_pages: list[int] = []
    estimated_scanned: bool = False
    text_quality_report: TextQualityReport | None = None
    recommended_pipeline: PipelineType = PipelineType.NATIVE

    @property
    def text_quality_score(self) -> float:
        """Convenience accessor for the overall quality score."""
        if self.text_quality_report is None:
            return 0.0
        return self.text_quality_report.overall_score
