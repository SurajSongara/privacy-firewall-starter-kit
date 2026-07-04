"""``detect`` CLI command — scan a PDF for PII using configured detectors."""

from pathlib import Path
from typing import Annotated

import typer

from privacy_firewall.detectors import (
    AadhaarDetector,
    DetectorRegistry,
    EmailDetector,
    PANDetector,
    PhoneDetector,
    UpiDetector,
)
from privacy_firewall.engine.fusion import FusionEngine
from privacy_firewall.parsers.pdf_parser import PDFParser


def _build_registry(detector_names: list[str] | None) -> DetectorRegistry:
    """Build a DetectorRegistry with the requested (or all) detectors.

    Args:
        detector_names: List of detector names to include, or ``None`` for all.

    Returns:
        A populated DetectorRegistry.
    """
    all_detectors: dict[str, type] = {
        "pan": PANDetector,
        "aadhaar": AadhaarDetector,
        "email": EmailDetector,
        "phone": PhoneDetector,
        "upi": UpiDetector,
    }

    registry = DetectorRegistry()
    names = detector_names if detector_names else list(all_detectors)
    for name in names:
        cls = all_detectors.get(name)
        if cls is None:
            msg = f"Unknown detector: {name!r}. Available: {', '.join(sorted(all_detectors))}"
            raise typer.BadParameter(msg)
        registry.register(cls())
    return registry


def detect_cmd(
    input_pdf: Annotated[
        Path,
        typer.Argument(help="Path to the PDF file to scan.", exists=True, dir_okay=False),
    ],
    detector: Annotated[
        list[str] | None,
        typer.Option(
            "--detector",
            "-d",
            help="Detector(s) to run (repeatable). Runs all if omitted.",
        ),
    ] = None,
    no_fuse: Annotated[
        bool,
        typer.Option("--no-fuse", help="Skip fusion (show raw detections)."),
    ] = False,
) -> None:
    """Run PII detectors on a PDF and list all detections found."""
    parser = PDFParser(input_pdf)
    document = parser.parse()

    registry = _build_registry(detector)
    result = registry.run_all(document)

    detections = result.detections
    if not no_fuse:
        engine = FusionEngine()
        fused = engine.fuse(detections)
        detections = fused.detections

    typer.echo(f"Detections ({len(detections)}):")
    for i, d in enumerate(detections, start=1):
        typer.echo(
            f"  {i:>3}. Page {d.page_number} | {d.detection_type:8s} | {d.text!r:30s} "
            f"| confidence={d.confidence:.2f} | detector={d.detector_name}"
        )
