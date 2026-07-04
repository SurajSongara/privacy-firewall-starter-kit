"""Generate synthetic PII test documents for the benchmark dataset.

All data is fictional — no real personal information is used.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _simple_pii() -> tuple[str, str]:
    """Return (pdf_path_relative_to_examples, ground_truth_dict)."""
    lines = [
        "CONFIDENTIAL STATEMENT",
        "",
        "PAN: AAAAA1111A",
        "Aadhaar: 2345 6789 0123",
        "Email: jane.smith@example.com",
        "Phone: +91-9876543210",
        "UPI: jane@paytm",
    ]
    ground_truth = {
        "document": "benchmark/datasets/simple-pii/document.pdf",
        "description": "Single page with one of each PII type",
        "expectations": [
            {"detection_type": "PAN", "text": "AAAAA1111A",
             "page_number": 1, "count": 1},
            {"detection_type": "AADHAAR", "text": "234567890123",
             "page_number": 1, "count": 1},
            {"detection_type": "EMAIL", "text": "jane.smith@example.com",
             "page_number": 1, "count": 1},
            {"detection_type": "PHONE", "text": "+91-9876543210",
             "page_number": 1, "count": 1},
            {"detection_type": "UPI", "text": "jane@paytm",
             "page_number": 1, "count": 1},
        ],
    }
    return "\n".join(lines), json.dumps(ground_truth, indent=2)


def _multi_pii() -> tuple[str, str]:
    """Return (pdf_text, ground_truth_json)."""
    lines = [
        "MONTHLY REPORT — MARCH 2026",
        "",
        "Employee: John Mathews",
        "PAN: ABCPA5678J",
        "",
        "Bank Details:",
        "Account: 123456789012",
        "IFSC: HDFC0001234",
        "UPI: john.m@okhdfcbank",
        "Phone: +91-9988776655",
        "",
        "--- Page Break ---",
        "",
        "Client Invoices",
        "PAN: FGHLA9012P",
        "Email: billing@client.in",
        "Phone: 022-45678900",
    ]
    ground_truth = {
        "document": "benchmark/datasets/multi-pii/document.pdf",
        "description": "Multi-page document with repeated PII values across pages",
        "expectations": [
            {"detection_type": "AADHAAR", "text": "123456789012", "page_number": 1, "count": 1},
            {"detection_type": "PAN", "text": "ABCPA5678J", "page_number": 1, "count": 1},
            {"detection_type": "UPI", "text": "john.m@okhdfcbank", "page_number": 1, "count": 1},
            {"detection_type": "PHONE", "text": "+91-9988776655", "page_number": 1, "count": 1},
            {"detection_type": "PAN", "text": "FGHLA9012P", "page_number": 2, "count": 1},
            {"detection_type": "EMAIL", "text": "billing@client.in", "page_number": 2, "count": 1},
        ],
    }
    return "\n".join(lines), json.dumps(ground_truth, indent=2)


def _no_pii() -> tuple[str, str]:
    """Return (pdf_text, ground_truth_json)."""
    lines = [
        "GENERAL NOTICE",
        "",
        "This document contains no personal information.",
        "It is used as a negative test case.",
        "",
        "Regards,",
        "Administrator",
    ]
    ground_truth = {
        "document": "benchmark/datasets/no-pii/document.pdf",
        "description": "Clean document with no PII — should produce zero detections",
        "expectations": [],
    }
    return "\n".join(lines), json.dumps(ground_truth, indent=2)


DATASETS: dict[str, tuple[str, str]] = {
    "simple-pii": _simple_pii(),
    "multi-pii": _multi_pii(),
    "no-pii": _no_pii(),
}


def main() -> None:
    """Generate all synthetic PDFs and ground-truth JSON files."""
    for name, (text, gt_json) in DATASETS.items():
        gt = json.loads(gt_json)
        pdf_rel = gt["document"]
        pdf_path = (HERE / pdf_rel).resolve()
        pdf_path.parent.mkdir(parents=True, exist_ok=True)

        gt_path = pdf_path.with_name("ground-truth.json")

        # Generate PDF using PyMuPDF
        import fitz  # type: ignore[import-untyped]

        doc = fitz.open()
        pages = text.split("\n\n--- Page Break ---\n\n")
        for page_text in pages:
            page = doc.new_page()
            page.insert_text(fitz.Point(50, 100), page_text, fontsize=11)
        doc.save(str(pdf_path))
        doc.close()

        # Write ground-truth
        gt_path.write_text(gt_json, encoding="utf-8")

        print(f"  [OK] {pdf_rel}")


if __name__ == "__main__":
    main()
