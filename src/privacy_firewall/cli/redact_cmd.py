"""``redact`` CLI command — produce a redacted PDF copy."""

from pathlib import Path
from typing import Annotated

import typer

from privacy_firewall.cli.detect_cmd import _build_registry
from privacy_firewall.engine.fusion import FusionEngine
from privacy_firewall.engine.redaction import RedactionPlanner, RedactionType
from privacy_firewall.parsers.pdf_parser import PDFParser
from privacy_firewall.renderer.pdf_renderer import PDFRenderer


def redact_cmd(
    input_pdf: Annotated[
        Path,
        typer.Argument(help="Path to the original PDF.", exists=True, dir_okay=False),
    ],
    output_pdf: Annotated[
        Path,
        typer.Argument(help="Path for the redacted PDF."),
    ],
    redaction_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="Redaction style: replace, black-bar, or highlight.",
        ),
    ] = "replace",
    detector: Annotated[
        list[str] | None,
        typer.Option(
            "--detector",
            "-d",
            help="Detector(s) to run (repeatable). Runs all if omitted.",
        ),
    ] = None,
    values_only: Annotated[
        bool,
        typer.Option(
            "--values-only",
            help="Redact only the matched value text, keeping labels visible.",
        ),
    ] = False,
) -> None:
    """Scan a PDF for PII and produce a redacted copy."""
    type_map: dict[str, RedactionType] = {
        "replace": RedactionType.REPLACE,
        "black-bar": RedactionType.BLACK_BAR,
        "highlight": RedactionType.HIGHLIGHT,
    }
    rtype = type_map.get(redaction_type)
    if rtype is None:
        choices = ", ".join(sorted(type_map))
        msg = f"Unknown redaction type: {redaction_type!r}. Choose from: {choices}"
        raise typer.BadParameter(msg)

    parser = PDFParser(input_pdf)
    document = parser.parse()

    registry = _build_registry(detector)
    result = registry.run_all(document, values_only=values_only)

    engine = FusionEngine()
    fused = engine.fuse(result.detections)

    planner = RedactionPlanner()
    plan = planner.plan(document, fused.detections, default_type=rtype)

    renderer = PDFRenderer()
    out_path = renderer.render(input_pdf, output_pdf, plan)

    typer.echo(f"Redacted PDF saved to: {out_path}")
    typer.echo(f"Redactions applied: {plan.total_redactions}")
