Status: PHASE_5_COMPLETE — all F006–F008 shipped; 657 tests passing

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

## Phase 4 — Trust & Recall Pack (Complete)

F001–F005 (see `tasks/README.md` for the delivered list):

- F001: `MarkResult(added, skipped)` → honest api/mark feedback; renderer
  merges overlapping same-type redaction rects.
- F002: bare 10-digit numbers in transaction-reference context are dropped
  (not parked in the ask band); PHONE 75% → 100% precision, recall intact.
- F003: per-character glyph boundaries from `rawdict` drive sub-word mark
  bboxes and the UI drag selection (`cx` in `/api/text`); proportional
  fallback only for OCR words.
- F004: workspace memory — `TermsStore` in `.privacy-firewall/terms.json`;
  remembered marks are pre-suggested (never pre-decided) in every workspace
  document; keep-allowlist; forget is workspace-wide. Supersedes P010.
- F005: `NameDetector` derives NAME candidates from email local parts,
  profile handles, and the page-1 title line; two evidence kinds → 0.9,
  one → 0.6 (ask), title-only → nothing. Heuristic fusion tier.

## Phase 5 — CA Beachhead Pack (Complete)

Committed to the CA / tax-practitioner segment (see the beachhead decision record
under `.claude/plans` for the viability + competitor teardown). F006–F008:

- F006: `redact-batch <folder>` — whole-folder redaction reusing the single-file
  pipeline (extracted to `engine/redact.py`), `redaction-summary.{csv,json}`,
  continue-on-error, non-zero exit on any error or failed verification.
- F007: `engine/verification.py` — re-parses the redacted output, proves no
  redacted value is still extractable and no detector re-fires, and emits a
  shareable `Certificate` (JSON + one-page PDF, no raw PII). `--certificate` on
  `redact`/`redact-batch`.
- F008: `GSTINDetector` — 15-char format + base-36 checksum + GST state code,
  registered via the new `ALL_DETECTORS` single source of truth.

Not built (gated on demand validation): packaged desktop installer (GTM enabler).

## Environment notes

- Python >= 3.12 (project runs on 3.14). Default OCR engine is resolved
  deterministically (`PRIVACY_FIREWALL_OCR_ENGINE` env → `rapidocr > tesseract >
  paddleocr`, skipping unavailable backends); `paddleocr` registers but reports
  unavailable on 3.14 (no `paddlepaddle` wheel).
- 9 detectors. 657 tests passing, ruff clean, mypy strict clean.
