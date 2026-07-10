"""``detect`` CLI command — scan a PDF for PII using configured detectors."""

from pathlib import Path
from typing import Annotated

import typer

from privacy_firewall.detectors import (
    AadhaarDetector,
    AccountDetector,
    DetectorRegistry,
    EmailDetector,
    IFSCDetector,
    PANDetector,
    PhoneDetector,
    UpiDetector,
)
from privacy_firewall.engine.context import ContextScorer
from privacy_firewall.engine.fusion import FusionEngine
from privacy_firewall.engine.ocr_pipeline import get_merged_document, get_pipeline_summary


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
        "ifsc": IFSCDetector,
        "account": AccountDetector,
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


def _engine_help() -> str:
    from privacy_firewall.ocr import list_engines

    engines = list_engines()
    default = engines[0] if engines else "(none)"
    return f"OCR engine to use. Available: {', '.join(engines)}. [default: {default}]"


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
    values_only: Annotated[
        bool,
        typer.Option(
            "--values-only",
            help="Use per-span bounding boxes (shows precise match regions).",
        ),
    ] = False,
    ocr: Annotated[
        bool,
        typer.Option("--ocr", help="Run OCR and merge with native text."),
    ] = False,
    auto: Annotated[
        bool,
        typer.Option("--auto", help="Auto-detect pipeline (native/OCR/hybrid)."),
    ] = False,
    ocr_engine: Annotated[
        str | None,
        typer.Option("--ocr-engine", help=_engine_help()),
    ] = None,
) -> None:
    """Run PII detectors on a PDF and list all detections found."""
    document, source = get_merged_document(
        input_pdf, force_ocr=ocr, auto=auto, ocr_provider=ocr_engine,
    )

    registry = _build_registry(detector)
    result = registry.run_all(document, values_only=values_only)

    detections = ContextScorer().apply(document, result.detections)
    if not no_fuse:
        engine = FusionEngine()
        fused = engine.fuse(detections)
        detections = fused.detections

    typer.echo(f"Pipeline: {get_pipeline_summary(source)}")
    typer.echo(f"Detections ({len(detections)}):")
    for i, d in enumerate(detections, start=1):
        typer.echo(
            f"  {i:>3}. Page {d.page_number} | {d.detection_type:8s} | {d.text!r:30s} "
            f"| confidence={d.confidence:.2f} | detector={d.detector_name}"
        )
