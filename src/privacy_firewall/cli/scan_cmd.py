"""``scan`` CLI command — parse a PDF and list its pages and blocks."""

from pathlib import Path
from typing import Annotated

import typer

from privacy_firewall.engine.ocr_pipeline import get_merged_document, get_pipeline_summary
from privacy_firewall.models.blocks import ImageBlock, TextBlock


def scan_cmd(
    input_pdf: Annotated[
        Path,
        typer.Argument(help="Path to the PDF file to scan.", exists=True, dir_okay=False),
    ],
    ocr: Annotated[
        bool,
        typer.Option("--ocr", help="Run OCR and merge with native text."),
    ] = False,
    auto: Annotated[
        bool,
        typer.Option("--auto", help="Auto-detect pipeline (native/OCR/hybrid)."),
    ] = False,
) -> None:
    """Parse a PDF and display its structure (pages, blocks, text previews)."""
    document, source = get_merged_document(input_pdf, force_ocr=ocr, auto=auto)

    typer.echo(f"Pipeline: {get_pipeline_summary(source)}")
    typer.echo(f"Pages: {len(document.pages)}")
    for page in document.pages:
        typer.echo(f"Page {page.page_number} ({page.width:.0f} x {page.height:.0f}):")
        for block in page.blocks:
            if isinstance(block, TextBlock):
                preview = block.text[:60] + "..." if len(block.text) > 60 else block.text
                typer.echo(f"  [TextBlock]  bbox=({block.bbox}) {preview!r}")
            elif isinstance(block, ImageBlock):
                size = len(block.image_data) if block.image_data else 0
                typer.echo(f"  [ImageBlock] bbox=({block.bbox}) {size} bytes")
