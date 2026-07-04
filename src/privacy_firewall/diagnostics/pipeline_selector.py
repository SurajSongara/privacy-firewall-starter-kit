"""Pipeline selection logic that chooses the optimal processing pipeline."""
from __future__ import annotations

from privacy_firewall.diagnostics.models import PipelineType


class PipelineSelector:
    """Selects the optimal processing pipeline based on document diagnostics.

    The selector applies a series of rules in decreasing priority —
    encryption, emptiness, scan status, text quality — and returns a
    ``PipelineType`` recommendation.
    """

    SCANNED_IMAGE_THRESHOLD = 3
    """Average images per page above which the document is considered scanned."""

    LOW_QUALITY_THRESHOLD = 0.3
    """Below this score the document is routed to OCR."""

    MEDIUM_QUALITY_THRESHOLD = 0.7
    """Below this score a hybrid pipeline is recommended."""

    SCANNED_QUALITY_THRESHOLD = 0.2
    """If quality is below this *and* any images exist, the doc is scanned."""

    @classmethod
    def select(
        cls,
        is_encrypted: bool = False,
        page_count: int = 1,
        has_native_text: bool = True,
        estimated_scanned: bool = False,
        text_quality_score: float = 1.0,
    ) -> PipelineType:
        """Choose the best pipeline for the given diagnostic parameters.

        Decision order:
        1. Encrypted documents always use OCR.
        2. Zero-page documents always use OCR.
        3. Scanned documents use OCR.
        4. No native text uses OCR.
        5. Low-quality text (< ``LOW_QUALITY_THRESHOLD``) uses OCR.
        6. Medium-quality text (< ``MEDIUM_QUALITY_THRESHOLD``) uses Hybrid.
        7. Otherwise Native is recommended.

        Args:
            is_encrypted: Whether the PDF requires a password.
            page_count: Number of pages.
            has_native_text: Whether extractable text was found.
            estimated_scanned: Whether the document appears scanned.
            text_quality_score: Quality score in ``[0.0, 1.0]``.

        Returns:
            The recommended ``PipelineType``.
        """
        if is_encrypted or page_count == 0:
            return PipelineType.OCR

        if estimated_scanned:
            return PipelineType.OCR

        if not has_native_text:
            return PipelineType.OCR

        if text_quality_score < cls.LOW_QUALITY_THRESHOLD:
            return PipelineType.OCR

        if text_quality_score < cls.MEDIUM_QUALITY_THRESHOLD:
            return PipelineType.HYBRID

        return PipelineType.NATIVE

    @classmethod
    def estimate_scanned(
        cls,
        page_count: int = 0,
        image_count: int = 0,
        text_quality_score: float = 1.0,
    ) -> bool:
        """Heuristically determine if a document is a scanned image.

        A document is considered scanned if it has a high image-to-page
        ratio, or a moderate image count combined with very low text quality.

        Args:
            page_count: Number of pages.
            image_count: Number of embedded images.
            text_quality_score: Quality score in ``[0.0, 1.0]``.

        Returns:
            ``True`` if the document appears to be a scan.
        """
        if page_count == 0:
            return False

        avg_images = image_count / page_count

        if avg_images > cls.SCANNED_IMAGE_THRESHOLD:
            return True

        return avg_images > 0 and text_quality_score < cls.SCANNED_QUALITY_THRESHOLD
