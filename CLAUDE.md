# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable, with dev extras)
pip install -e ".[dev]"

# Run the CLI (Typer app, entry point in src/privacy_firewall/__main__.py)
python -m privacy_firewall scan   TestFiles/sbi_statement.pdf
python -m privacy_firewall detect TestFiles/statement1-5.pdf --ocr
python -m privacy_firewall redact input.pdf out.pdf --values-only
python -m privacy_firewall doctor  TestFiles/statement1-5.pdf     # combined diagnostics + layout + OCR recommendation
python -m privacy_firewall diagnostics <pdf>                       # DocumentAnalyzer only

# Tests (pytest is configured with pythonpath=["src"], testpaths=["tests"])
pytest                                                  # full suite
pytest tests/detectors/test_pan_detector.py -v          # single file
pytest tests/detectors/test_pan_detector.py::test_x -v  # single test
pytest --cov                                            # coverage (source = privacy_firewall)

# Lint / format / type-check
ruff check src/ tests/
ruff format src/ tests/
mypy src/                                               # strict mode, pydantic plugin enabled
```

Python `>=3.12` is required (project runs on 3.14). CLI script entry point is `privacy-firewall = "privacy_firewall.__main__:entry_point"`.

## Workflow rules (from `.ai/WORKFLOW_RULES.md`)

- Work exclusively on the `dev` branch — never push directly to `main`.
- Every task ships as a PR from `dev` → `main`; do **not** merge without explicit user approval.
- If a force push closes an existing PR, open a new one.

## Engine rules (from `.ai/ENGINE_RULES.md`)

- Deterministic before AI; regex beats LLM; LLM is optional.
- Engine has no framework dependencies — CLI is a thin wrapper around engine components (zero business logic in `cli/`).
- Detection, planning, and rendering are separated (see pipeline below).
- Every `Detection` carries evidence (matched text, span, bbox) and a confidence score.
- Never modify original documents — renderer writes to a new output path.

## Architecture

Pipeline (each stage returns immutable Pydantic v2 models):

```
PDFParser.parse()          → Document (Page[Block[...]])
OCRProvider.process()      → Document                          # optional
HybridMerger.merge()       → Document                          # IoU=0.5 dedup of native+OCR
DetectorRegistry.run_all() → DetectionResult                   # list[Detection] + per-detector timing
FusionEngine.fuse()        → FusionResult                      # overlap resolution by priority tier + confidence
RedactionPlanner.plan()    → RedactionPlan                     # list[Redaction] (REPLACE | BLACK_BAR | HIGHLIGHT)
PDFRenderer.render()       → new PDF file                      # destructive: apply_redactions() strips text/images
```

Central orchestrator: `engine/ocr_pipeline.py::get_merged_document()` decides between native / OCR-only / hybrid based on `DocumentAnalyzer` diagnostics (used by the `--auto` CLI flag).

Module map (see `AGENTS.md` for the full per-file reference — it is the source of truth for design details):

- `models/` — frozen Pydantic dataclasses: `BoundingBox`, `Span`, `TextBlock`/`ImageBlock`/`TableBlock`, `Detection`, `Document`. Universal vocabulary — every other module depends on it.
- `parsers/pdf_parser.py` — PyMuPDF; groups per-word `TextSpan`s from `page.get_text("words")` under blocks from `page.get_text("dict")`.
- `ocr/` — `OCRProvider` ABC + `OCRProviderRegistry` singleton in `ocr/__init__.py` that auto-registers adapters at import time via try/except ImportError. Adapters: `TesseractOCRAdapter` (default), `PaddleOCRAdapter`, plus `rapid.py` and additional `tesseract.py` variants under `adapters/`.
- `detectors/` — `BaseDetector` ABC + `DetectorRegistry`. Each detector: `PAN`, `Aadhaar`, `Email`, `Phone`, `UPI`, `IFSC`, `Account`. Deduplication helpers in `detectors/utils.py` (`is_exact_duplicate`, `is_containment_duplicate`). Detectors are pure: `(Document) → list[Detection]`; testable in isolation.
- `engine/fusion.py` — priority tiers `regex=5 > validator=4 > heuristic=3 > ner=2 > llm=1`; groups by `(page, detection_type)`, sorts by `(span.start, -priority, -confidence)`, merges overlapping neighbours.
- `engine/redaction.py` — `RedactionType.{REPLACE, BLACK_BAR, HIGHLIGHT}`. REPLACE/BLACK_BAR use `page.add_redact_annot()` + `page.apply_redactions()` (physically strips from the content stream); HIGHLIGHT is a visual overlay only.
- `engine/hybrid_merger.py` — merges native + OCR `Document`s, preferring native and adding OCR blocks whose bbox has IoU ≤ 0.5 with any native block.
- `diagnostics/` — `DocumentAnalyzer` produces a `DiagnosticReport` with a weighted `TextQualityReport` (printable ratio 0.30, replacement chars 0.20, fragmentation 0.15, long tokens 0.20, whitespace 0.15) and a `PipelineSelector` decision (NATIVE / OCR / HYBRID).
- `layout/analyzer.py` — classifies blocks into HEADER/FOOTER/PAGE_NUMBER/paragraphs by page position + vertical gap threshold.
- `bank_profiler/` — per-bank profilers (SBI, HDFC, ICICI, Axis, Generic) matched by IFSC prefix + account-number regex; registry returns highest-confidence match.
- `cli/` — one file per subcommand (`scan_cmd`, `detect_cmd`, `redact_cmd`, `diagnostics_cmd`, `doctor_cmd`); wired in `__main__.py`. `_safe()` helper sanitises Unicode for the Windows cp1252 console.

## Common flags

- `--ocr` / `--auto` / `--ocr-engine <name>` on `scan`/`detect`/`redact` — force OCR, let the diagnostics recommend, or pick a specific engine from the OCR registry.
- `--values-only` (redact) — redact only the PII value while keeping surrounding labels.
- `--type replace|black-bar|highlight` (redact) — redaction visual mode.
- `--detector <name>` / `--no-fuse` (detect) — filter to one detector or skip fusion.

## Notes for future sessions

- `AGENTS.md` is a hand-maintained deep-dive reference generated from the source; consult it before changing architecture but assume drift is possible — verify against code.
- `.ai/CURRENT_STATE.md` tracks phase status; `tasks/` contains one markdown file per outstanding task (Phase 2 “Robustness Pack” R001–R010, most complete). Update `CURRENT_STATE.md` when finishing a task.
- Known false positives on `TestFiles/statement1-5.pdf`: Aadhaar detector catches 12-digit UPI txn refs, Phone detector catches 10-digit bank refs, Email detector catches OCR artifacts like `30524@sbi.coin`. Aadhaar Verhoeff + structural filtering in ref strings is the pending fix.
- `paddlepaddle` has no wheel for Python 3.14 — `PaddleOCRAdapter` will fail to register; Tesseract remains the working default.
