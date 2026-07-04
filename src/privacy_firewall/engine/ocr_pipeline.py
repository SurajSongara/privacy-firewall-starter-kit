"""OCR pipeline — decides whether to invoke OCR and merges results."""
from __future__ import annotations

from pathlib import Path

from privacy_firewall.diagnostics import DocumentAnalyzer, PipelineType
from privacy_firewall.engine.hybrid_merger import HybridMerger
from privacy_firewall.models.document import Document
from privacy_firewall.ocr import PaddleOCRAdapter


def get_merged_document(
    pdf_path: Path,
    *,
    force_ocr: bool = False,
    auto: bool = False,
    native_doc: Document | None = None,
) -> tuple[Document, str]:
    """Return the best available document for detection.

    Args:
        pdf_path: Path to the PDF file.
        force_ocr: When ``True``, always run OCR and merge with native.
        auto: When ``True``, run diagnostics and decide automatically.
        native_doc: Pre-parsed native document (avoids re-parsing).

    Returns:
        A ``(document, source)`` tuple where *source* is one of
        ``"native"``, ``"ocr"``, or ``"hybrid"``.
    """
    from privacy_firewall.parsers.pdf_parser import PDFParser

    # Always have native available
    if native_doc is None:
        native_doc = PDFParser(pdf_path).parse()

    # No OCR requested → native
    if not force_ocr and not auto:
        return native_doc, "native"

    # Auto mode: decide based on diagnostics
    if auto:
        report = DocumentAnalyzer(pdf_path).analyze()
        pipeline = report.recommended_pipeline
        if pipeline == PipelineType.NATIVE:
            return native_doc, "native"

    # Run OCR
    ocr_doc = _run_ocr(pdf_path)

    # OCR only (no native text) → pure OCR
    if not native_doc.pages or all(
        not any(hasattr(b, "text") and b.text for b in p.blocks)
        for p in native_doc.pages
    ):
        return ocr_doc, "ocr"

    # Hybrid: merge native + OCR
    merge_result = HybridMerger.merge(native_doc, ocr_doc)
    return merge_result.document, "hybrid"


def _run_ocr(pdf_path: Path) -> Document:
    """Run PaddleOCR on a PDF file.

    Args:
        pdf_path: Path to the PDF.

    Returns:
        A ``Document`` with OCR-extracted blocks.

    Raises:
        ImportError: If paddleocr is not installed.
    """
    adapter = PaddleOCRAdapter()
    return adapter.process(pdf_path)


def get_pipeline_summary(source: str) -> str:
    """Return a human-readable summary of the pipeline used.

    Args:
        source: The pipeline source string.

    Returns:
        A descriptive string.
    """
    summaries = {
        "native": "Native text extraction",
        "ocr": "Full OCR processing",
        "hybrid": "Hybrid (native + OCR merge)",
    }
    return summaries.get(source, f"Unknown ({source})")
