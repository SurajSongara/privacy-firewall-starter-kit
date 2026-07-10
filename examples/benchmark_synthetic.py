"""Benchmark the privacy firewall against synthetic documents.

Compares expected PII (from ground truth) against actual detections.
"""

from __future__ import annotations

import json
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from privacy_firewall.cli.detect_cmd import _build_registry
from privacy_firewall.engine.fusion import FusionEngine
from privacy_firewall.parsers.pdf_parser import PDFParser


def run_detection(pdf_path: Path, use_ocr: bool = False) -> list[dict]:
    """Run detection on a PDF and return results."""
    parser = PDFParser(pdf_path)
    document = parser.parse()

    registry = _build_registry(None)  # All detectors
    result = registry.run_all(document, values_only=False)

    engine = FusionEngine()
    fused = engine.fusion.fuse(result.detections) if hasattr(engine, 'fusion') else result.detections

    return [
        {
            "detection_type": d.detection_type,
            "text": d.text,
            "page_number": d.page_number,
        }
        for d in (fused if isinstance(fused, list) else fused.detections)
    ]


def compare_results(expected: list[dict], actual: list[dict]) -> dict:
    """Compare expected vs actual detections."""
    # Normalize texts for comparison
    def normalize(text: str) -> str:
        return text.replace(" ", "").replace("-", "").replace("+91", "").lower()

    matched = []
    missed = []
    false_positives = []

    # Check expected items
    for exp in expected:
        exp_type = exp.get("detection_type", "")
        exp_text = normalize(exp.get("text", ""))

        found = False
        for act in actual:
            if act["detection_type"] == exp_type and normalize(act["text"]) == exp_text:
                matched.append(exp)
                found = True
                break

        if not found:
            missed.append(exp)

    # Check for false positives (actual detections not in expected)
    for act in actual:
        act_text = normalize(act["text"])
        found_in_expected = False
        for exp in expected:
            if exp.get("detection_type") == act["detection_type"] and normalize(exp.get("text", "")) == act_text:
                found_in_expected = True
                break
        if not found_in_expected:
            false_positives.append(act)

    return {
        "matched": len(matched),
        "missed": len(missed),
        "false_positives": len(false_positives),
        "total_expected": len(expected),
        "total_actual": len(actual),
        "recall": len(matched) / len(expected) if expected else 1.0,
        "precision": len(matched) / len(actual) if actual else 1.0,
        "missed_details": missed,
        "fp_details": false_positives,
    }


def main():
    """Run benchmark on all synthetic documents."""
    synthetic_dir = Path(__file__).resolve().parent / "synthetic"

    results = []

    for json_path in sorted(synthetic_dir.glob("*.json")):
        if json_path.name == "summary.json":
            continue

        with open(json_path) as f:
            ground_truth = json.load(f)

        pdf_name = ground_truth["document"].split("/")[-1]
        pdf_path = synthetic_dir / pdf_name

        if not pdf_path.exists():
            print(f"  [SKIP] {pdf_name} - PDF not found")
            continue

        # Filter expectations to only include types we detect
        detectable_types = {"PAN", "AADHAAR", "EMAIL", "PHONE", "UPI", "ACCOUNT", "IFSC"}
        expected = [
            e for e in ground_truth.get("expectations", [])
            if e.get("detection_type") in detectable_types
        ]

        print(f"\n  Testing: {pdf_name}")
        print(f"  Expected PII: {len(expected)} items")

        actual = run_detection(pdf_path)
        print(f"  Detected: {len(actual)} items")

        comparison = compare_results(expected, actual)

        print(f"  Matched: {comparison['matched']}/{comparison['total_expected']}")
        print(f"  Recall: {comparison['recall']:.1%}")
        print(f"  Precision: {comparison['precision']:.1%}")
        print(f"  False Positives: {comparison['false_positives']}")

        if comparison['missed_details']:
            print(f"  Missed:")
            for m in comparison['missed_details']:
                print(f"    - {m['detection_type']}: {m['text']}")

        if comparison['fp_details']:
            print(f"  False Positives:")
            for fp in comparison['fp_details']:
                print(f"    - {fp['detection_type']}: {fp['text']}")

        results.append({
            "file": pdf_name,
            **comparison,
        })

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_expected = sum(r["total_expected"] for r in results)
    total_matched = sum(r["matched"] for r in results)
    total_fp = sum(r["false_positives"] for r in results)

    print(f"  Total Expected: {total_expected}")
    print(f"  Total Matched: {total_matched}")
    print(f"  Total False Positives: {total_fp}")
    print(f"  Overall Recall: {total_matched/total_expected:.1%}" if total_expected else "  No expected items")


if __name__ == "__main__":
    main()
