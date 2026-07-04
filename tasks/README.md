# Task Tracker

## Phase 1 — Core Engine (Complete ✅)

All 15 tasks in `tasks/completed/` — repository bootstrap through project review.

Delivered:
- PII Detection & Redaction Engine with 6 detectors
- CLI (scan/detect/redact), destructive redaction, values-only mode
- 231 tests, ruff clean, mypy clean

## Phase 2 — Ingestion Robustness

Focus on document robustness before adding more detectors.

Principles: Diagnose first → OCR only when needed → Preserve layout → Benchmark every change

| # | Task | Status |
|---|------|--------|
| R001 | Document Diagnostics | Pending |
| R002 | Text Quality Heuristics | Pending |
| R003 | Pipeline Selector | Pending |
| R004 | OCR Provider Interface | Pending |
| R005 | PaddleOCR Integration | Pending |
| R006 | Hybrid Merge | Pending |
| R007 | Layout Analyzer | Pending |
| R008 | Bank Profile | Pending |
| R009 | Doctor CLI | Pending |
| R010 | Regression Suite | Pending |

## Workflow

1. Read `.ai/START_HERE.md`
2. Pick the next pending task by number
3. Implement, test, lint, commit
4. Update `CURRENT_STATE.md`
5. Stop for review — never batch tasks
