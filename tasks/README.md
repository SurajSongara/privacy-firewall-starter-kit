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

P010 (feedback memory) stays deferred until the review UI has real usage, per its spec.

## Workflow

1. Read `.ai/START_HERE.md`
2. Pick the next pending task by number
3. Implement, test, lint, commit
4. Update `CURRENT_STATE.md`
5. Stop for review — never batch tasks
