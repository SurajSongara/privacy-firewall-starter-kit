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

## Phase 3 — Precision & Review Pack (Planned)

The core gap: detection and decision are conflated — every detection becomes a redaction, but what counts as PII depends on the document and the sharing context. Phase 3 separates them (Detect → Decide → Review → Redact), fixes the known false positives, and adds a local review UI with engine pre-selections.

Principles: Precision before UI → Policy decides, user overrides → ReviewPlan JSON is the engine/UI contract → UI holds zero business logic

| # | Task | Status |
|---|------|--------|
| P001 | Detection Evidence — `detection_id` + `reasons` on Detection | ✅ Complete |
| P002 | Context Scoring — label-proximity confidence adjustment | ✅ Complete |
| P003 | FP Fixes — Aadhaar first-digit rule, email TLD allowlist | ✅ Complete |
| P004 | Precision Benchmark — FP tracking + regression baseline | ✅ Complete |
| P005 | Policy Profiles — YAML: redact/keep/ask per type + bands | ✅ Complete |
| P006 | Decision Engine — (Fusion, Policy) → ReviewPlan JSON | ✅ Complete |
| P007 | Plan CLI — `--plan`, `--interactive`, `--yes` | ✅ Complete |
| P008 | Page Image Renderer — PNG + bbox transform for UI | ✅ Complete |
| P009 | Review Web UI — local, offline, `privacy-firewall review` | ✅ Complete |
| P010 | Feedback Memory — opt-in allowlists from review decisions | ⏸ Deferred |

Delivered:
- Context scoring (label proximity promotes/demotes; drops below 0.3)
- Precision baseline: 100% precision+recall on 6/7 types; PHONE 75% precision (2 known UTR/Ref-ID traps land in the ask band)
- Policy presets `share-with-ai` / `kyc` / `minimal` + custom YAML/JSON
- ReviewPlan JSON with source hash verification — the engine/CLI/UI contract and audit record
- `detect --plan/--policy`, `redact --plan --interactive|--yes`
- `privacy-firewall review file.pdf` — offline web UI (optional extra `[ui]`)

P010 (feedback memory) was deferred until the review UI had real usage; F004 un-defers it at workspace scope.

## Phase 3.5 — Studio & Review UX (Complete ✅, shipped ad hoc)

Post-P009 work delivered outside the task tracker: Studio dashboard with multi-format ingestion (images/txt/md/docx → PDF), style-matched star redactions, layout-stable redaction (surviving line text no longer shifts), review UI overhaul (two-row header, zoom, view-result), partial-word drag selection with editable mark popup, and instance-scoped renderer bbox search (repeated-text stars stay styled, per-instance keep/redact honoured).

## Phase 4 — Trust & Recall Pack (Planned)

Close the gaps real usage exposed: honest UI feedback, the last known FP class, exact redaction geometry, and the two features that end repetitive manual marking.

Principles: Redaction boxes must be glyph-exact → Remembered marks are suggestions, not decisions → Deterministic name evidence before NER

| # | Task | Status |
|---|------|--------|
| F001 | Review UX Polish — honest mark feedback + overlapping-rect merge | ⏳ Pending |
| F002 | Phone Precision — UTR/Ref-ID trap demotion (≥0.9 precision) | ⏳ Pending |
| F003 | Char Geometry — rawdict per-char bboxes; exact sub-word redaction | ⏳ Pending |
| F004 | Workspace Memory — remembered marks across documents (P010 scope) | ⏳ Pending |
| F005 | Name Detection — deterministic NAME detector from document evidence | ⏳ Pending |

## Workflow

1. Read `.ai/START_HERE.md`
2. Pick the next pending task by number
3. Implement, test, lint, commit
4. Update `CURRENT_STATE.md`
5. Stop for review — never batch tasks
