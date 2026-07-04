# Examples & Benchmark Dataset

## Overview

This directory contains synthetic example documents and a benchmark dataset for
the Privacy Firewall PII Detection & Redaction Engine.

All documents are **synthetically generated** — no real personal information is
used.

## Structure

```
examples/
├── README.md                         # This file
├── generate_samples.py               # Script to (re)generate synthetic PDFs
└── benchmark/
    ├── README.md                     # Benchmark description & usage
    └── datasets/
        ├── simple-pii/
        │   ├── document.pdf          # Single-page PDF with one of each PII type
        │   └── ground-truth.json     # Expected detections for scoring
        ├── multi-pii/
        │   ├── document.pdf          # Multi-page PDF with repeated PII
        │   └── ground-truth.json
        └── no-pii/
            ├── document.pdf          # Clean document with no PII
            └── ground-truth.json
```

## Ground-Truth Format

Each `ground-truth.json` file follows this schema:

```json
{
  "document": "document.pdf",
  "description": "Brief description of the test case",
  "expectations": [
    {
      "detection_type": "PAN|AADHAAR|EMAIL|PHONE|UPI",
      "text": "exact matched text",
      "page_number": 1,
      "count": 1
    }
  ]
}
```

- `detection_type`: The PII type label (must match detector output).
- `text`: The exact string the detector should find.
- `page_number`: 1-based page where the PII appears.
- `count`: How many times this value should be detected on that page.

## Generating Samples

Run the generator script to produce the PDF documents:

```bash
python examples/generate_samples.py
```

This creates `document.pdf` in each dataset subdirectory using only synthetic
data. The ground-truth JSON files are pre-committed and do not change.
