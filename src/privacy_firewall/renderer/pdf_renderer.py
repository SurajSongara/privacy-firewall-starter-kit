"""PDF rendering: applies redaction instructions from a plan onto a PDF copy."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import fitz

from privacy_firewall.engine.redaction import RedactionPlan, RedactionType


class PDFRenderer:
    """Applies a RedactionPlan to a PDF file, producing a redacted copy.

    Uses PyMuPDF's redaction annotations (``add_redact_annot`` +
    ``apply_redactions``) to *physically remove* text and images
    underneath each redaction region — not merely draw on top.

    The original PDF is never modified.
    """

    BLACK_BAR_COLOR: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """RGB colour used for ``BLACK_BAR`` redactions."""

    REPLACE_FILL: tuple[float, float, float] = (1.0, 1.0, 1.0)
    """Background colour behind the replacement text for ``REPLACE``."""

    REPLACE_TEXT_COLOR: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Colour of the replacement text for ``REPLACE`` redactions."""

    DEFAULT_REPLACEMENT = "*****"
    """Replacement drawn when a ``REPLACE`` redaction carries no text."""

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

        Redactions are applied directly to an in-memory copy of the source
        PDF, then saved to *output_path*. The original file is never touched.

        Args:
            input_path: Path to the original PDF (never modified).
            output_path: Where to write the redacted copy.
            plan: The redaction plan to apply.

        Returns:
            The absolute path to the output file.
        """
        doc = fitz.open(str(input_path))
        try:
            self._apply_plan(doc, plan)
            doc.save(str(output_path))
        finally:
            doc.close()

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
        doc = fitz.open(stream=data, filetype="pdf")
        try:
            PDFRenderer._apply_plan(doc, plan)
            result = cast(bytes, doc.tobytes())
        finally:
            doc.close()

        return result

    @staticmethod
    def _apply_plan(doc: Any, plan: RedactionPlan) -> None:
        """Apply every redaction in the plan to the open PyMuPDF document.

        For REPLACE / BLACK_BAR redactions this uses
        ``add_redact_annot`` + ``apply_redactions``, which physically
        strips the underlying text/images.  HIGHLIGHT redactions use
        ``draw_rect`` (visual-only).

        Uses PyMuPDF's ``search_for`` to find the exact text bbox for
        precise redaction, falling back to the detection bbox if not found.

        Args:
            doc: An open PyMuPDF document.
            plan: The redaction plan to apply.
        """
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_redactions = plan.by_page(page_num + 1)
            if not page_redactions:
                continue

            has_destructive = False
            for redaction in page_redactions:
                # Try to find the exact text bbox using PyMuPDF's search
                search_results = page.search_for(redaction.detection.text)

                if search_results:
                    # Redact ALL occurrences of this text
                    rects = search_results
                else:
                    # Fall back to the detection bbox
                    rects = [
                        fitz.Rect(
                            redaction.bbox.x0,
                            redaction.bbox.y0,
                            redaction.bbox.x1,
                            redaction.bbox.y1,
                        )
                    ]

                for rect in rects:
                    if redaction.redaction_type == RedactionType.REPLACE:
                        # Strip the text and draw the replacement (e.g. "*****")
                        # on a white background instead of a black bar.
                        page.add_redact_annot(
                            rect,
                            text=redaction.replacement_text or PDFRenderer.DEFAULT_REPLACEMENT,
                            fill=PDFRenderer.REPLACE_FILL,
                            text_color=PDFRenderer.REPLACE_TEXT_COLOR,
                            align=fitz.TEXT_ALIGN_CENTER,
                        )
                        has_destructive = True
                    elif redaction.redaction_type == RedactionType.BLACK_BAR:
                        page.add_redact_annot(rect, text="", fill=PDFRenderer.BLACK_BAR_COLOR)
                        has_destructive = True
                    elif redaction.redaction_type == RedactionType.HIGHLIGHT:
                        page.draw_rect(
                            rect,
                            color=None,
                            fill=PDFRenderer.HIGHLIGHT_COLOR,
                            fill_opacity=PDFRenderer.HIGHLIGHT_OPACITY,
                            width=0,
                        )

            if has_destructive:
                page.apply_redactions()
