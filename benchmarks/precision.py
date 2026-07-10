"""Precision/recall evaluation against the labeled synthetic dataset.

Runs the full detection pipeline (parse → detect → context-score → fuse)
on every labeled PDF in ``examples/synthetic`` and scores the detections
against the ground-truth expectations. Per-detector precision and recall
are compared to a checked-in baseline so regressions fail the test suite.

Refresh the baseline after an intentional metrics change:

    python -m benchmarks.precision --update
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

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
from privacy_firewall.parsers.pdf_parser import PDFParser

SYNTHETIC_DIR = Path(__file__).resolve().parent.parent / "examples" / "synthetic"
BASELINE_PATH = SYNTHETIC_DIR / "precision_baseline.json"

DETECTABLE_TYPES = {"PAN", "AADHAAR", "EMAIL", "PHONE", "UPI", "ACCOUNT", "IFSC"}


def _normalize(text: str) -> str:
    """Normalise a PII value for comparison across formatting variants."""
    text = text.lower()
    if text.startswith("+91"):
        text = text[3:]
    return re.sub(r"[\s\-().]", "", text)


@dataclass
class TypeMetrics:
    """Per-detection-type counts and derived metrics."""

    tp: int = 0
    fp: int = 0
    fn: int = 0
    fp_examples: list[str] = field(default_factory=list)
    fn_examples: list[str] = field(default_factory=list)

    @property
    def precision(self) -> float:
        """Fraction of detections that were expected."""
        total = self.tp + self.fp
        return self.tp / total if total else 1.0

    @property
    def recall(self) -> float:
        """Fraction of expected items that were detected."""
        total = self.tp + self.fn
        return self.tp / total if total else 1.0


def _detect(pdf_path: Path) -> list[tuple[str, str, int]]:
    """Run the full pipeline; return ``(type, normalised_text, page)`` triples."""
    document = PDFParser(pdf_path).parse()

    registry = DetectorRegistry()
    for detector in (
        PANDetector(),
        AadhaarDetector(),
        EmailDetector(),
        PhoneDetector(),
        UpiDetector(),
        IFSCDetector(),
        AccountDetector(),
    ):
        registry.register(detector)

    detections = registry.run_all(document).detections
    detections = ContextScorer().apply(document, detections)
    detections = FusionEngine().fuse(detections).detections
    return [(d.detection_type, _normalize(d.text), d.page_number) for d in detections]


def evaluate(synthetic_dir: Path = SYNTHETIC_DIR) -> dict[str, TypeMetrics]:
    """Score every labeled synthetic document; aggregate metrics per type.

    Matching is by ``(detection_type, normalised text)`` — page number is
    deliberately ignored because repeated values legitimately appear on
    multiple pages.

    Args:
        synthetic_dir: Directory of ``<name>.pdf`` + ``<name>.json`` pairs.

    Returns:
        Mapping of detection type to aggregated metrics.
    """
    metrics: dict[str, TypeMetrics] = {t: TypeMetrics() for t in sorted(DETECTABLE_TYPES)}

    for json_path in sorted(synthetic_dir.glob("*.json")):
        if json_path.name in ("summary.json", BASELINE_PATH.name):
            continue
        ground_truth = json.loads(json_path.read_text())
        pdf_path = synthetic_dir / ground_truth["document"].split("/")[-1]
        if not pdf_path.exists():
            continue

        expected = {
            (e["detection_type"], _normalize(e["text"]))
            for e in ground_truth.get("expectations", [])
            if e["detection_type"] in DETECTABLE_TYPES
        }
        actual = {(t, text) for t, text, _ in _detect(pdf_path)}

        for dtype, text in expected & actual:
            metrics[dtype].tp += 1
        for dtype, text in expected - actual:
            metrics[dtype].fn += 1
            metrics[dtype].fn_examples.append(f"{pdf_path.name}: {text}")
        for dtype, text in actual - expected:
            metrics[dtype].fp += 1
            metrics[dtype].fp_examples.append(f"{pdf_path.name}: {text}")

    return metrics


def to_baseline_dict(metrics: dict[str, TypeMetrics]) -> dict[str, dict[str, float]]:
    """Convert metrics to the JSON-serialisable baseline structure."""
    return {
        dtype: {"precision": round(m.precision, 4), "recall": round(m.recall, 4)}
        for dtype, m in sorted(metrics.items())
    }


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, dict[str, float]]:
    """Load the checked-in baseline metrics."""
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def main() -> None:
    """Print current metrics; ``--update`` rewrites the baseline file."""
    import sys

    metrics = evaluate()
    for dtype, m in sorted(metrics.items()):
        print(
            f"{dtype:8s} precision={m.precision:.2%} recall={m.recall:.2%} "
            f"(tp={m.tp} fp={m.fp} fn={m.fn})"
        )
        for example in m.fp_examples:
            print(f"         FP: {example}")
        for example in m.fn_examples:
            print(f"         FN: {example}")

    if "--update" in sys.argv:
        BASELINE_PATH.write_text(json.dumps(to_baseline_dict(metrics), indent=2) + "\n")
        print(f"\nBaseline written to {BASELINE_PATH}")


if __name__ == "__main__":
    main()
