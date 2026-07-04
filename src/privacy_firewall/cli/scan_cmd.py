"""``scan`` CLI command — parse a PDF and list its pages and blocks."""

from pathlib import Path
from typing import Annotated

import typer

from privacy_firewall.models.blocks import ImageBlock, TextBlock
from privacy_firewall.parsers.pdf_parser import PDFParser


def scan_cmd(
    input_pdf: Annotated[
        Path,
        typer.Argument(help="Path to the PDF file to scan.", exists=True, dir_okay=False),
    ],
) -> None:
    """Parse a PDF and display its structure (pages, blocks, text previews)."""
    parser = PDFParser(input_pdf)
    document = parser.parse()

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
