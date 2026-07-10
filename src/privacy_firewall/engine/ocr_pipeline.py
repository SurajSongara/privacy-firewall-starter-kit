"""OCR pipeline — decides whether to invoke OCR and merges results."""
from __future__ import annotations

from pathlib import Path

from privacy_firewall.diagnostics import DocumentAnalyzer, PipelineType
from privacy_firewall.engine.hybrid_merger import HybridMerger
from privacy_firewall.models.document import Document
from privacy_firewall.ocr.provider import OCRProvider


def get_merged_document(
    pdf_path: Path,
    *,
    force_ocr: bool = False,
    auto: bool = False,
    native_doc: Document | None = None,
    ocr_provider: str | None = None,
) -> tuple[Document, str]:
    """Return the best available document for detection.

    Args:
        pdf_path: Path to the PDF file.
        force_ocr: When ``True``, always run OCR and merge with native.
        auto: When ``True``, run diagnostics and decide automatically.
        native_doc: Pre-parsed native document (avoids re-parsing).
        ocr_provider: OCR adapter name.  ``None`` uses the registry default.

    Returns:
        A ``(document, source)`` tuple where *source* is one of
        ``"native"``, ``"ocr"``, or ``"hybrid"``.
    """
    from privacy_firewall.parsers.pdf_parser import PDFParser

    if native_doc is None:
        native_doc = PDFParser(pdf_path).parse()

    if not force_ocr and not auto:
        return native_doc, "native"

    if auto:
        report = DocumentAnalyzer(pdf_path).analyze()
        pipeline = report.recommended_pipeline
        if pipeline == PipelineType.NATIVE:
            return native_doc, "native"

    ocr_doc = _run_ocr(pdf_path, provider=ocr_provider)

    if not native_doc.pages or all(
        not any(hasattr(b, "text") and b.text for b in p.blocks)
        for p in native_doc.pages
    ):
        return ocr_doc, "ocr"

    merge_result = HybridMerger.merge(native_doc, ocr_doc)
    return merge_result.document, "hybrid"


def _run_ocr(pdf_path: Path, provider: str | None = None) -> Document:
    """Run the chosen OCR adapter on a PDF file.

    Args:
        pdf_path: Path to the PDF.
        provider: OCR adapter name, or ``None`` for registry default.

    Returns:
        A ``Document`` with OCR-extracted blocks.

    Raises:
        ImportError: If the required OCR package is not installed.
    """
    adapter = _get_adapter(provider)
    return adapter.process(pdf_path)


def _get_adapter(name: str | None = None) -> OCRProvider:
    """Look up an OCR adapter from the global registry.

    Args:
        name: Adapter name, or ``None`` for the registry default.

    Returns:
        An ``OCRProvider`` instance.

    Raises:
        ValueError: If the name is unknown or no default is set.
    """
    from privacy_firewall.ocr import get_registry

    registry = get_registry()

    if name is None:
        cls = registry.get_default()
        if cls is None:
            msg = (
                "No OCR engine available. Install one of:\n"
                "  pip install tesserocr   (Tesseract)\n"
                "  pip install paddleocr   (PaddleOCR)"
            )
            raise ValueError(msg)
        return cls()

    cls = registry.get(name)
    if cls is None:
        available = ", ".join(registry.names) or "(none)"
        msg = f"Unknown OCR engine: {name!r}. Available: {available}"
        raise ValueError(msg)
    return cls()


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
