# Task Tracker

## Phase 1 — Core Engine (Complete ✅)

All 15 tasks in `tasks/completed/` — repository bootstrap through project review.

Delivered:
- PII Detection & Redaction Engine with 6 detectors
- CLI (scan/detect/redact), destructive redaction, values-only mode
- 231 tests, ruff clean, mypy clean

## Phase 2 — Ingestion Robustness (Complete ✅)

Focus on document robustness before adding more detectors.

Principles: Diagnose first → OCR only when needed → Preserve layout → Benchmark every change

| # | Task | Status |
|---|------|--------|
| R001 | Document Diagnostics | ✅ Complete |
| R002 | Text Quality Heuristics | ✅ Complete |
| R003 | Pipeline Selector | ✅ Complete |
| R004 | OCR Provider Interface | ✅ Complete |
| R005 | PaddleOCR Integration | ✅ Complete |
| R006 | Hybrid Merge | ✅ Complete |
| R007 | Layout Analyzer | ✅ Complete |
| R008 | Bank Profile | ✅ Complete |
| R009 | Doctor CLI | ✅ Complete |
| R010 | Regression Suite | ✅ Complete |

Delivered:
- Document diagnostics with text quality scoring (5 heuristics)
- Pipeline selector (native/OCR/hybrid recommendation)
- OCR provider interface + registry + PaddleOCR adapter
- Hybrid merge (native + OCR into unified Document)
- Layout analyzer (headers, footers, paragraphs, tables, reading order)
- Bank profiler for SBI/HDFC/ICICI/Axis/generic
- `privacy-firewall doctor` CLI command
- Regression benchmarks with synthetic PDFs + recall tests

## Workflow

1. Read `.ai/START_HERE.md`
2. Pick the next pending task by number
3. Implement, test, lint, commit
4. Update `CURRENT_STATE.md`
5. Stop for review — never batch tasks
