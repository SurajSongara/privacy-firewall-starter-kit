"""Data models for document diagnostics."""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict


class PipelineType(enum.StrEnum):
    """Recommended processing pipeline for a document."""

    NATIVE = "native"
    """Document has high-quality extractable text — use native parser."""

    OCR = "ocr"
    """Document is scanned or has very low text quality — use OCR."""

    HYBRID = "hybrid"
    """Mixed content — extract native text where possible, OCR the rest."""


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
        text_quality_score: Float in ``[0.0, 1.0]`` estimating text quality.
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
    text_quality_score: float = 1.0
    recommended_pipeline: PipelineType = PipelineType.NATIVE
