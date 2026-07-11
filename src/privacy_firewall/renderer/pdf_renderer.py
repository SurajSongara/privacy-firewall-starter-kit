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
    """Fallback background colour behind ``REPLACE`` text."""

    REPLACE_TEXT_COLOR: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Fallback colour of the ``REPLACE`` replacement text."""

    DEFAULT_REPLACEMENT = "*****"
    """Replacement drawn when a ``REPLACE`` redaction carries no text."""

    DEFAULT_FONT_SIZE = 11.0
    """Fallback font size when the original style cannot be sampled."""

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
                        # Strip the text and draw stars styled like the
                        # original content: same font size, a matching
                        # base-14 font family, the original text colour,
                        # and the sampled background colour — so the
                        # replacement blends into the surrounding layout.
                        fontname, fontsize, text_color = PDFRenderer._sample_text_style(page, rect)
                        fill = PDFRenderer._sample_background(page, rect)
                        replacement = redaction.replacement_text or PDFRenderer.DEFAULT_REPLACEMENT
                        replacement = PDFRenderer._fit_stars(replacement, rect, fontsize)
                        page.add_redact_annot(
                            rect,
                            text=replacement,
                            fontname=fontname,
                            fontsize=fontsize,
                            fill=fill,
                            text_color=text_color,
                            align=fitz.TEXT_ALIGN_LEFT,
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

    @staticmethod
    def _sample_text_style(page: Any, rect: Any) -> tuple[str, float, tuple[float, float, float]]:
        """Dominant text style (base-14 font, size, colour) inside *rect*.

        Samples the spans that overlap the redaction rectangle before the
        text is stripped, so the replacement stars can match the original
        content. Falls back to Helvetica at a size derived from the rect
        height (covers OCR'd scans, where there is no real text layer).
        """
        best_area = 0.0
        font = ""
        size = 0.0
        color = 0
        try:
            for block in page.get_text("dict", clip=rect).get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        overlap = fitz.Rect(span["bbox"]) & rect
                        area = max(overlap.width, 0.0) * max(overlap.height, 0.0)
                        if area > best_area:
                            best_area = area
                            font = span.get("font", "")
                            size = float(span.get("size", 0.0))
                            color = int(span.get("color", 0))
        except Exception:  # noqa: BLE001 - style matching must never block redaction
            best_area = 0.0

        if best_area <= 0.0 or size <= 0.0:
            fallback = max(4.0, min(PDFRenderer.DEFAULT_FONT_SIZE, rect.height * 0.75))
            return "helv", fallback, PDFRenderer.REPLACE_TEXT_COLOR
        rgb = (
            ((color >> 16) & 255) / 255.0,
            ((color >> 8) & 255) / 255.0,
            (color & 255) / 255.0,
        )
        return PDFRenderer._base14_for(font), min(size, rect.height), rgb

    @staticmethod
    def _base14_for(font: str) -> str:
        """Nearest base-14 family for an embedded font name.

        Redaction replacement text can only use standard fonts, so exact
        matching is impossible — but keeping the family (mono / serif /
        sans) preserves the look of the surrounding content.
        """
        name = font.lower()
        if "courier" in name or "mono" in name:
            return "cour"
        if "times" in name or "georgia" in name or "garamond" in name or "book" in name:
            return "tiro"
        return "helv"

    @staticmethod
    def _sample_background(page: Any, rect: Any) -> tuple[float, float, float]:
        """Most common pixel colour on the border just outside *rect*.

        Approximates the local background (white page, coloured table row,
        dark header band) so the redaction patch doesn't punch a white
        hole into coloured areas.
        """
        try:
            pad = 2.0
            clip = fitz.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad)
            clip = clip & page.rect
            pix = page.get_pixmap(clip=clip)
            w, h = pix.width, pix.height
            if w < 3 or h < 3:
                return PDFRenderer.REPLACE_FILL
            counts: dict[tuple[int, ...], int] = {}
            border = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)]
            border += [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
            for x, y in border:
                value = tuple(pix.pixel(x, y)[:3])
                counts[value] = counts.get(value, 0) + 1
            most_common = max(counts, key=lambda k: counts[k])
            return (most_common[0] / 255.0, most_common[1] / 255.0, most_common[2] / 255.0)
        except Exception:  # noqa: BLE001 - style matching must never block redaction
            return PDFRenderer.REPLACE_FILL

    @staticmethod
    def _fit_stars(replacement: str, rect: Any, fontsize: float) -> str:
        """Trim a star-only replacement so it cannot overflow the rect.

        ``apply_redactions`` drops replacement text that doesn't fit its
        rectangle, which would leave a blank patch instead of stars.
        Non-star replacements are returned unchanged.
        """
        if not replacement or set(replacement) != {"*"}:
            return replacement
        char_width = fitz.get_text_length("*", fontname="helv", fontsize=fontsize)
        if char_width <= 0:
            return replacement
        max_chars = max(1, int(rect.width / char_width))
        return replacement[:max_chars]
