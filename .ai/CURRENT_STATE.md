Status: PHASE_4_PLANNED — Phases 1–3 complete (+ Studio/Review UX shipped ad hoc); next task F001

## Phase 1 — Core Engine (Complete)

- Repository setup (TASK-001)
- Document Model (TASK-002)
- PDF Parser (TASK-003)
- Detector SDK (TASK-004)
- Regex Framework (TASK-005)
- PAN Detector (TASK-006)
- Aadhaar Detector (TASK-007)
- Contact Detectors — Email, Phone, UPI (TASK-008)
- Fusion Engine (TASK-009)
- Redaction Planner (TASK-010)
- PDF Renderer — destructive redaction (TASK-011)
- CLI Commands — scan, detect, redact (TASK-012)
- --values-only flag for precise value-level redaction (TASK-013)
- Golden Dataset — examples/ with benchmark structure (TASK-014)
- Project Review — architecture review, refactor, docs (TASK-015)

## Phase 2 — Ingestion Robustness (Complete)

R001–R010: diagnostics + text-quality scoring, pipeline selector (native/OCR/hybrid),
OCR provider interface + adapters, hybrid merge, layout analyzer, bank profiler
(SBI/HDFC/ICICI/Axis/generic), `doctor` CLI, regression suite.

## Phase 3 — Precision & Review Pack (Complete; P010 superseded by F004)

P001–P009: detection evidence (`detection_id` + `reasons`), context scoring,
FP fixes (Aadhaar first-digit + Verhoeff, email TLD allowlist), precision
benchmark, policy profiles (`share-with-ai` / `kyc` / `minimal`), decision
engine → ReviewPlan JSON contract, plan CLI (`--plan/--interactive/--yes`),
page image renderer, offline review web UI (`privacy-firewall review`).

Pipeline:

```
PDF/Image -> Parser (+OCR/hybrid) -> Document -> Detectors -> Fusion
          -> DecisionEngine (policy) -> ReviewPlan (user review) -> Planner -> Renderer
```

## Phase 3.5 — Studio & Review UX (Complete, shipped ad hoc)

- Studio dashboard (`privacy-firewall` with no args): workspace document list,
  uploads, multi-format ingestion (images/txt/md/docx converted to PDF once).
- Style-matched star redactions + layout-stable redaction (affected lines are
  removed whole and surviving characters re-inserted at original origins).
- Review UI overhaul: two-row header, real zoom, page nav, preview mode,
  view-result after apply.
- Partial-word drag selection (proportional char mapping) with editable mark
  popup; search-to-mark card.
- Renderer: instance-scoped bbox search + rect dedupe — repeated-text stars
  stay styled and per-instance keep/redact decisions are honoured.

## Phase 4 — Trust & Recall Pack (Planned — next task F001)

Tasks F001–F005 in `tasks/` (see `tasks/README.md`). Build order:
review UX polish (F001) → phone precision (F002) → exact char geometry (F003)
→ workspace memory (F004) → name detection (F005).

Known issues Phase 4 addresses:

- "No new matches" toast conflates already-marked with not-found (F001).
- Overlapping detector + manual rects double-draw stars (F001).
- PHONE precision 75% — UTR/Ref-ID traps on statement1-5.pdf (F002).
- Sub-word bboxes interpolated proportionally — inexact on proportional
  fonts; block-text/span order mismatch on glyph-heavy PDFs corrupts manual
  mark geometry (F003).
- Manual marks don't carry across documents in a workspace (F004).
- No NAME detector — names are always manual marks today (F005).

## Environment notes

- Python >= 3.12 (project runs on 3.14); `paddlepaddle` has no 3.14 wheel, so
  the PaddleOCR adapter fails to register — Tesseract is the working default.
- 586 tests passing, ruff clean, mypy strict clean.
