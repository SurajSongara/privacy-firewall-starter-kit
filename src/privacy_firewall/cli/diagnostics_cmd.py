"""``diagnostics`` CLI command — analyse a PDF and report its health."""
from pathlib import Path
from typing import Annotated

import typer

from privacy_firewall.diagnostics import DocumentAnalyzer


def diagnostics_cmd(
    input_pdf: Annotated[
        Path,
        typer.Argument(help="Path to the PDF file to diagnose.", exists=True, dir_okay=False),
    ],
) -> None:
    """Analyse a PDF and display its diagnostic report."""
    analyzer = DocumentAnalyzer(input_pdf)
    report = analyzer.analyze()

    typer.echo(f"File:           {report.file_path}")
    typer.echo(f"Pages:          {report.page_count}")
    typer.echo(f"Images:         {report.image_count}")
    typer.echo(f"Native text:    {'yes' if report.has_native_text else 'no'}")
    typer.echo(f"Encrypted:      {'yes' if report.is_encrypted else 'no'}")
    typer.echo(f"Rotated pages:  {report.rotated_pages or 'none'}")
    typer.echo(f"Estimated scan: {'yes' if report.estimated_scanned else 'no'}")
    typer.echo(f"Pipeline:       {report.recommended_pipeline.value}")

    tqr = report.text_quality_report
    if tqr is not None:
        typer.echo("")
        typer.echo("--- Text Quality ---")
        typer.echo(f"  Overall:        {tqr.overall_score:.4f}")
        typer.echo(f"  Printable:      {tqr.printable_ratio:.4f}")
        typer.echo(f"  Replace penalty:{tqr.replace_penalty:.4f}")
        typer.echo(f"  Fragmentation:  {tqr.fragmentation_score:.4f}")
        typer.echo(f"  Token quality:  {tqr.token_quality:.4f}")
        typer.echo(f"  Whitespace:     {tqr.whitespace_ratio:.4f}")
        if tqr.reasons:
            typer.echo(f"  Issues: {', '.join(tqr.reasons)}")
    else:
        typer.echo(f"  Text quality:   {report.text_quality_score:.4f}")
