"""PDF rendering: applies redaction instructions from a plan onto a PDF copy."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import fitz

from privacy_firewall.engine.redaction import Redaction, RedactionPlan, RedactionType


class PDFRenderer:
    """Applies a RedactionPlan to a PDF file, producing a redacted copy.

    The original PDF is never modified. All redactions are drawn onto the
    output copy using PyMuPDF's page drawing primitives.
    """

    BLACK_BAR_COLOR: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """RGB colour used for ``BLACK_BAR`` and ``REPLACE`` redactions."""

    HIGHLIGHT_COLOR: tuple[float, float, float] = (1.0, 1.0, 0.0)
    """RGB colour used for ``HIGHLIGHT`` redactions."""

    HIGHLIGHT_OPACITY: float = 0.3
    """Opacity (0-1) applied to highlight overlays."""

    def render(
        self,
        input_path: str | Path,
        output_path: str | Path,
        plan: RedactionPlan,
    ) -> Path:
        """Generate a redacted PDF copy.

        Args:
            input_path: Path to the original PDF (never modified).
            output_path: Where to write the redacted copy.
            plan: The redaction plan to apply.

        Returns:
            The absolute path to the output file.
        """
        src = fitz.open(str(input_path))
        out = fitz.open()

        try:
            for page_num in range(len(src)):
                src_page = src[page_num]
                out_page = out.new_page(
                    width=src_page.rect.width,
                    height=src_page.rect.height,
                )
                out_page.show_pdf_page(
                    out_page.rect,
                    src,
                    page_num,
                )

                page_redactions = plan.by_page(page_num + 1)
                for redaction in page_redactions:
                    self._apply_redaction(out_page, redaction)

            out.save(str(output_path))
        finally:
            src.close()
            out.close()

        return Path(output_path).resolve()

    @staticmethod
    def render_bytes(data: bytes, plan: RedactionPlan) -> bytes:
        """Generate a redacted PDF from raw bytes.

        Args:
            data: Raw bytes of the original PDF.
            plan: The redaction plan to apply.

        Returns:
            Raw bytes of the redacted PDF.
        """
        src = fitz.open(stream=data, filetype="pdf")
        out = fitz.open()

        try:
            for page_num in range(len(src)):
                src_page = src[page_num]
                out_page = out.new_page(
                    width=src_page.rect.width,
                    height=src_page.rect.height,
                )
                out_page.show_pdf_page(
                    out_page.rect,
                    src,
                    page_num,
                )

                page_redactions = plan.by_page(page_num + 1)
                for redaction in page_redactions:
                    PDFRenderer._apply_redaction(out_page, redaction)

            result = cast(bytes, out.tobytes())
        finally:
            src.close()
            out.close()

        return result

    @staticmethod
    def _apply_redaction(page: Any, redaction: Redaction) -> None:
        """Draw a redaction annotation onto a single page.

        Args:
            page: A PyMuPDF Page object.
            redaction: The redaction instruction to apply.
        """
        rect = fitz.Rect(
            redaction.bbox.x0,
            redaction.bbox.y0,
            redaction.bbox.x1,
            redaction.bbox.y1,
        )

        if redaction.redaction_type in (RedactionType.REPLACE, RedactionType.BLACK_BAR):
            page.draw_rect(
                rect,
                color=None,
                fill=PDFRenderer.BLACK_BAR_COLOR,
                width=0,
            )
        elif redaction.redaction_type == RedactionType.HIGHLIGHT:
            page.draw_rect(
                rect,
                color=None,
                fill=PDFRenderer.HIGHLIGHT_COLOR,
                fill_opacity=PDFRenderer.HIGHLIGHT_OPACITY,
                width=0,
            )
