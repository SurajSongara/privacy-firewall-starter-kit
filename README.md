# Privacy Firewall

Offline-first PII Detection & Redaction Engine.

Detect and redact sensitive information from PDF documents — entirely offline.

## Features

- **6 detectors**: PAN, Aadhaar, Email, Phone, UPI, plus a generic regex framework
- **Destructive redaction**: Text is physically stripped from the PDF content stream (not just visually overlaid)
- **Values-only mode**: Redact only the PII value while preserving labels (`--values-only`)
- **Priority-based fusion**: Overlapping detections resolved by detector priority tiers
- **CLI-first**: Zero business logic in the CLI — all work delegated to engine components

## Quick Start

```bash
pip install -e ".[dev]"

# Scan — show document structure
python -m privacy_firewall scan input.pdf

# Detect — find PII
python -m privacy_firewall detect input.pdf

# Redact — produce a redacted copy
python -m privacy_firewall redact input.pdf output.pdf

# Values-only redaction — keep labels, redact only values
python -m privacy_firewall redact input.pdf output.pdf --values-only
```

## Project Structure

```
src/privacy_firewall/
├── __main__.py          # Typer CLI entry point
├── cli/                 # CLI commands (scan, detect, redact) — zero logic
├── models/              # Pydantic v2 frozen models
├── parsers/             # PyMuPDF PDF parser
├── detectors/           # BaseDetector ABC, registry, 6 detectors
├── engine/              # Fusion engine + redaction planner
└── renderer/            # PDF renderer (destructive redaction)

examples/                # Golden dataset for benchmarking
tests/                   # 231 tests (pytest, --cov)
```

## Current Status

Phase 1 complete. 231 tests, ruff clean, mypy clean.
See `.ai/CURRENT_STATE.md` for the latest status.

## Success Criteria

1. ✅ Parse PDFs
2. ✅ Detect Indian PII (PAN, Aadhaar, Email, Phone, UPI)
3. ✅ Produce redaction plan
4. ✅ Export redacted PDF (destructive, values-only mode)
5. ⏳ Achieve high benchmark recall (dataset + runner pending)

Start with `.ai/START_HERE.md`.
