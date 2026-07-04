"""PDF document analyser that produces diagnostic reports."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz

from privacy_firewall.diagnostics.models import DiagnosticReport, PipelineType
from privacy_firewall.diagnostics.text_quality import TextQualityAnalyzer


class DocumentAnalyzer:
    """Inspects a PDF file and produces a structured diagnostic report.

    The analyser opens the document with PyMuPDF, runs a series of checks
    (text presence, image count, rotation, encryption, ...), scores the
    quality of any extractable text, and recommends a processing pipeline.
    """

    SCANNED_IMAGE_THRESHOLD = 3
    """If average images per page exceeds this the document is likely a scan."""

    LOW_QUALITY_THRESHOLD = 0.3
    """Below this score the document is routed to OCR."""

    MEDIUM_QUALITY_THRESHOLD = 0.7
    """Below this score a hybrid pipeline is recommended."""

    def __init__(self, file_path: str | Path) -> None:
        """Initialise the analyser with a path to a PDF file.

        Args:
            file_path: Path to the PDF file to analyse.
        """
        self._path = Path(file_path)

    @staticmethod
    def from_bytes(data: bytes) -> DiagnosticReport:
        """Analyse PDF content from raw bytes.

        Args:
            data: Raw PDF bytes.

        Returns:
            A DiagnosticReport for the supplied content.
        """
        doc = fitz.open(stream=data, filetype="pdf")
        try:
            return DocumentAnalyzer._analyze_doc(doc, file_path="")
        finally:
            doc.close()

    def analyze(self) -> DiagnosticReport:
        """Open the PDF file and produce a diagnostic report.

        Returns:
            A DiagnosticReport with all fields populated.
        """
        doc = fitz.open(str(self._path))
        try:
            return self._analyze_doc(doc, file_path=str(self._path.resolve()))
        finally:
            doc.close()

    @staticmethod
    def _analyze_doc(doc: Any, file_path: str) -> DiagnosticReport:
        """Core analysis logic — inspects an open PyMuPDF document.

        Args:
            doc: An open PyMuPDF document.
            file_path: The file path string (empty for byte input).

        Returns:
            A populated DiagnosticReport.
        """
        page_count = len(doc)
        is_encrypted = doc.needs_pass or doc.is_encrypted

        if is_encrypted or page_count == 0:
            return DiagnosticReport(
                file_path=file_path,
                page_count=page_count,
                is_encrypted=is_encrypted,
                recommended_pipeline=PipelineType.OCR,
            )

        total_images = 0
        has_text = False
        rotated_pages: list[int] = []
        all_text = ""

        for i in range(page_count):
            page = doc[i]
            total_images += len(page.get_images())

            rotation = page.rotation or 0
            if rotation not in (0, 360):
                rotated_pages.append(i + 1)

            page_text = page.get_text("text") or ""
            if page_text.strip():
                has_text = True
                all_text += page_text + "\n"

        if not all_text:
            return DocumentAnalyzer._no_text_report(
                file_path, page_count, total_images, rotated_pages,
            )

        tqr = TextQualityAnalyzer.analyze(all_text)
        quality = tqr.overall_score
        est_scanned = DocumentAnalyzer._estimate_scanned(
            page_count, total_images, quality,
        )
        pipeline = DocumentAnalyzer._recommend_pipeline(
            has_text, quality, est_scanned,
        )

        return DiagnosticReport(
            file_path=file_path,
            page_count=page_count,
            image_count=total_images,
            has_native_text=has_text,
            rotated_pages=rotated_pages,
            estimated_scanned=est_scanned,
            text_quality_report=tqr,
            recommended_pipeline=pipeline,
        )

    @staticmethod
    def _no_text_report(
        file_path: str,
        page_count: int,
        image_count: int,
        rotated_pages: list[int],
    ) -> DiagnosticReport:
        """Build a report for documents that have no extractable text.

        Args:
            file_path: The file path string.
            page_count: Total page count.
            image_count: Total image count.
            rotated_pages: Pages that are rotated.

        Returns:
            A DiagnosticReport with OCR as the recommended pipeline.
        """
        est_scanned = DocumentAnalyzer._estimate_scanned(
            page_count, image_count, 0.0,
        )
        return DiagnosticReport(
            file_path=file_path,
            page_count=page_count,
            image_count=image_count,
            rotated_pages=rotated_pages,
            estimated_scanned=est_scanned,
            recommended_pipeline=PipelineType.OCR,
        )

    @staticmethod
    def _estimate_scanned(page_count: int, image_count: int, quality: float) -> bool:
        """Heuristically determine if a document is a scan.

        A document is considered scanned if it has a high image-to-page
        ratio *and* low text quality.

        Args:
            page_count: Total pages.
            image_count: Total embedded images.
            quality: Text quality score from ``_score_text_quality``.

        Returns:
            ``True`` if the document appears to be scanned.
        """
        if page_count == 0:
            return False
        avg_images = image_count / page_count
        return avg_images > DocumentAnalyzer.SCANNED_IMAGE_THRESHOLD or (
            avg_images > 0 and quality < 0.2
        )

    @staticmethod
    def _recommend_pipeline(
        has_text: bool,
        quality: float,
        estimated_scanned: bool,
    ) -> PipelineType:
        """Choose the best pipeline based on diagnostics.

        Args:
            has_text: Whether any extractable text was found.
            quality: Text quality score.
            estimated_scanned: Whether the doc appears scanned.

        Returns:
            The recommended PipelineType.
        """
        if estimated_scanned or not has_text or quality < DocumentAnalyzer.LOW_QUALITY_THRESHOLD:
            return PipelineType.OCR
        if quality < DocumentAnalyzer.MEDIUM_QUALITY_THRESHOLD:
            return PipelineType.HYBRID
        return PipelineType.NATIVE
