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

        REPLACE / BLACK_BAR redactions physically strip content via
        ``add_redact_annot`` + ``apply_redactions``. Because MuPDF
        *rewrites* any text line a redaction touches — losing the
        original kerning and shifting the surviving text sideways — the
        affected lines are removed whole and their surviving characters
        are re-inserted at their exact original positions afterwards.
        HIGHLIGHT redactions use ``draw_rect`` (visual-only).

        Each redaction's bbox is refined via ``search_for`` clipped to
        its own region (falling back to the detection bbox if not
        found), and identical rects from overlapping detections are
        deduplicated so no region is redacted twice.

        Args:
            doc: An open PyMuPDF document.
            plan: The redaction plan to apply.
        """
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_redactions = plan.by_page(page_num + 1)
            if not page_redactions:
                continue

            jobs: list[tuple[Any, RedactionType, str]] = []
            seen: set[tuple[float, float, float, float]] = set()
            for redaction in page_redactions:
                bbox_rect = fitz.Rect(
                    redaction.bbox.x0,
                    redaction.bbox.y0,
                    redaction.bbox.x1,
                    redaction.bbox.y1,
                )
                # Refine the bbox via search, but only inside this
                # redaction's own region: the plan carries one redaction
                # per instance, so a page-wide search of repeated text
                # (e.g. a marked substring) would return every twin and
                # the duplicate jobs would repaint their background fill
                # over the already-drawn styled stars.
                clip = fitz.Rect(
                    bbox_rect.x0 - 2, bbox_rect.y0 - 2, bbox_rect.x1 + 2, bbox_rect.y1 + 2
                )
                rects = page.search_for(redaction.detection.text, clip=clip)
                if not rects:
                    # Imprecise bbox (e.g. OCR geometry offset from the
                    # native text layer): search the whole page but keep
                    # only the match nearest this detection's bbox.
                    matches = page.search_for(redaction.detection.text)
                    if matches:
                        cx = (bbox_rect.x0 + bbox_rect.x1) / 2
                        cy = (bbox_rect.y0 + bbox_rect.y1) / 2
                        rects = [
                            min(
                                matches,
                                key=lambda r: (
                                    ((r.x0 + r.x1) / 2 - cx) ** 2 + ((r.y0 + r.y1) / 2 - cy) ** 2
                                ),
                            )
                        ]
                    else:
                        rects = [bbox_rect]
                for rect in rects:
                    key = tuple(round(v, 1) for v in (rect.x0, rect.y0, rect.x1, rect.y1))
                    if key in seen:
                        continue  # two detections of the same instance
                    seen.add(key)
                    if redaction.redaction_type == RedactionType.HIGHLIGHT:
                        page.draw_rect(
                            rect,
                            color=None,
                            fill=PDFRenderer.HIGHLIGHT_COLOR,
                            fill_opacity=PDFRenderer.HIGHLIGHT_OPACITY,
                            width=0,
                        )
                    else:
                        replacement = redaction.replacement_text or PDFRenderer.DEFAULT_REPLACEMENT
                        jobs.append((rect, redaction.redaction_type, replacement))

            if not jobs:
                continue
            try:
                PDFRenderer._redact_preserving_layout(page, jobs)
            except Exception:  # noqa: BLE001 - layout preservation is best-effort
                PDFRenderer._redact_legacy(page, jobs)

    @staticmethod
    def _redact_preserving_layout(page: Any, jobs: list[tuple[Any, RedactionType, str]]) -> None:
        """Redact *jobs* without disturbing the rest of each text line.

        MuPDF rewrites any line a redaction rectangle touches, which can
        shift the surviving text (kerned PDFs lose their spacing). To
        keep the layout pixel-stable:

        1. Snapshot every affected line's characters (text, position,
           font, size, colour) before touching the page.
        2. Remove those lines *whole* (text only — images and vector
           graphics untouched), so MuPDF never partially rewrites one.
        3. Clear image pixels inside the actual redaction rectangles
           (scanned documents carry their PII in the image).
        4. Re-insert the surviving characters at their original origins
           and draw the styled replacement stars / black bars.
        """
        rects = [job[0] for job in jobs]
        lines = PDFRenderer._snapshot_lines(page)

        # Lines hit by a redaction — chain-expanded so that any line
        # clipped by another affected line's removal band is also
        # captured and re-inserted rather than silently damaged.
        affected: list[dict[str, Any]] = []
        affected_ids: set[int] = set()
        pending = [ln for ln in lines if any(ln["rect"].intersects(r) for r in rects)]
        while pending:
            for line in pending:
                affected.append(line)
                affected_ids.add(id(line))
            bands = [ln["rect"] for ln in affected]
            pending = [
                ln
                for ln in lines
                if id(ln) not in affected_ids and any(ln["rect"].intersects(b) for b in bands)
            ]

        survivors: list[dict[str, Any]] = []
        anchors: dict[int, dict[str, Any]] = {}
        for line in affected:
            for span in line["spans"]:
                fontname = PDFRenderer._base14_for(span["font"])
                run: list[dict[str, Any]] = []
                run_width = 0.0

                def flush() -> None:
                    if run:
                        survivors.append(PDFRenderer._make_run(span, run))
                        run.clear()

                for char in span["chars"]:
                    hit = PDFRenderer._char_hit(char, rects)
                    if hit is not None:
                        flush()
                        # First redacted character anchors the replacement.
                        anchors.setdefault(
                            hit,
                            {
                                "origin": char["origin"],
                                "size": span["size"],
                                "color": span["color"],
                                "font": span["font"],
                            },
                        )
                        continue
                    if run:
                        # Split the run wherever the original glyph
                        # position deviates from the natural advance
                        # (kerning, or metrics differing from the
                        # base-14 replacement font) — every glyph must
                        # land exactly where it was.
                        expected_x = run[0]["origin"][0] + run_width
                        if abs(float(char["origin"][0]) - expected_x) > 0.3:
                            flush()
                    if not run:
                        run_width = 0.0
                    run.append(char)
                    run_width += fitz.get_text_length(
                        char["c"], fontname=fontname, fontsize=span["size"]
                    )
                flush()

        # Sample backgrounds before anything is stripped or cleared.
        fills = [
            PDFRenderer._sample_background(page, rect)
            if rtype == RedactionType.REPLACE
            else PDFRenderer.BLACK_BAR_COLOR
            for rect, rtype, _ in jobs
        ]

        # Pass 1: remove the affected lines' text — nothing else.
        if affected:
            for line in affected:
                page.add_redact_annot(line["rect"], fill=False)
            page.apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_NONE,
                graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                text=fitz.PDF_REDACT_TEXT_REMOVE,
            )

        # Pass 2: clear image pixels inside the redaction rects (scans).
        for rect, _rtype, _repl in jobs:
            page.add_redact_annot(rect, fill=False)
        page.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_PIXELS,
            graphics=fitz.PDF_REDACT_LINE_ART_NONE,
            text=fitz.PDF_REDACT_TEXT_REMOVE,
        )

        # Draw fills, then the styled stars, then the surviving text.
        for (rect, rtype, replacement), fill in zip(jobs, fills):
            page.draw_rect(rect, color=None, fill=fill, width=0)
            if rtype != RedactionType.REPLACE:
                continue
            anchor = anchors.get(id(rect))
            if anchor is not None:
                fontsize = float(anchor["size"])
                color = PDFRenderer._int_rgb(int(anchor["color"]))
                fontname = PDFRenderer._base14_for(str(anchor["font"]))
                origin = (rect.x0, float(anchor["origin"][1]))
            else:  # no text under the rect (scanned image region)
                fontsize = max(4.0, min(PDFRenderer.DEFAULT_FONT_SIZE, rect.height * 0.75))
                color = PDFRenderer.REPLACE_TEXT_COLOR
                fontname = "helv"
                origin = (rect.x0, rect.y1 - rect.height * 0.25)
            stars = PDFRenderer._fit_stars(replacement, rect, fontsize)
            page.insert_text(origin, stars, fontsize=fontsize, fontname=fontname, color=color)

        for survivor in survivors:
            page.insert_text(
                survivor["origin"],
                survivor["text"],
                fontsize=survivor["size"],
                fontname=PDFRenderer._base14_for(survivor["font"]),
                color=PDFRenderer._int_rgb(survivor["color"]),
            )

    @staticmethod
    def _redact_legacy(page: Any, jobs: list[tuple[Any, RedactionType, str]]) -> None:
        """Plain per-rect redaction (fallback if layout preservation fails)."""
        for rect, rtype, replacement in jobs:
            if rtype == RedactionType.REPLACE:
                fontname, fontsize, text_color = PDFRenderer._sample_text_style(page, rect)
                fill = PDFRenderer._sample_background(page, rect)
                page.add_redact_annot(
                    rect,
                    text=PDFRenderer._fit_stars(replacement, rect, fontsize),
                    fontname=fontname,
                    fontsize=fontsize,
                    fill=fill,
                    text_color=text_color,
                    align=fitz.TEXT_ALIGN_LEFT,
                )
            else:
                page.add_redact_annot(rect, text="", fill=PDFRenderer.BLACK_BAR_COLOR)
        page.apply_redactions()

    @staticmethod
    def _snapshot_lines(page: Any) -> list[dict[str, Any]]:
        """Capture every horizontal text line with per-character geometry.

        Raises:
            ValueError: If the page contains rotated (non-horizontal)
                text — the caller falls back to legacy redaction.
        """
        lines: list[dict[str, Any]] = []
        for block in page.get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = []
                rect = fitz.Rect()
                for span in line.get("spans", []):
                    chars = [
                        {"c": ch["c"], "bbox": ch["bbox"], "origin": ch["origin"]}
                        for ch in span.get("chars", [])
                    ]
                    if not chars:
                        continue
                    for ch in chars:
                        rect |= fitz.Rect(ch["bbox"])
                    spans.append(
                        {
                            "font": span.get("font", ""),
                            "size": float(span.get("size", PDFRenderer.DEFAULT_FONT_SIZE)),
                            "color": int(span.get("color", 0)),
                            "chars": chars,
                        }
                    )
                if not spans:
                    continue
                if abs(line.get("dir", (1, 0))[1]) > 0.01:
                    msg = "page has non-horizontal text"
                    raise ValueError(msg)
                lines.append({"rect": rect, "spans": spans})
        return lines

    @staticmethod
    def _char_hit(char: dict[str, Any], rects: list[Any]) -> int | None:
        """Id of the first rect containing the character's centre, else None."""
        x0, y0, x1, y1 = char["bbox"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for rect in rects:
            if rect.x0 <= cx <= rect.x1 and rect.y0 <= cy <= rect.y1:
                return id(rect)
        return None

    @staticmethod
    def _make_run(span: dict[str, Any], chars: list[dict[str, Any]]) -> dict[str, Any]:
        """Bundle consecutive surviving characters into one insertable run."""
        return {
            "text": "".join(ch["c"] for ch in chars),
            "origin": (float(chars[0]["origin"][0]), float(chars[0]["origin"][1])),
            "font": span["font"],
            "size": span["size"],
            "color": span["color"],
        }

    @staticmethod
    def _int_rgb(color: int) -> tuple[float, float, float]:
        """sRGB integer (as reported by ``get_text``) to a float triple."""
        return (
            ((color >> 16) & 255) / 255.0,
            ((color >> 8) & 255) / 255.0,
            (color & 255) / 255.0,
        )

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
