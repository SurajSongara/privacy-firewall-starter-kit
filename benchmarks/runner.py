"""Regression runner — compares diagnostics and recall against expected values."""
from __future__ import annotations

import dataclasses
from pathlib import Path

from privacy_firewall.diagnostics import DiagnosticReport, DocumentAnalyzer, PipelineType
from privacy_firewall.layout import LayoutAnalyzer
from privacy_firewall.parsers.pdf_parser import PDFParser

BENCHMARK_DIR = Path(__file__).parent


@dataclasses.dataclass
class BenchmarkExpectation:
    """Expected diagnostic results for a benchmark PDF."""

    name: str
    category: str
    file_path: str
    expected_pipeline: PipelineType
    min_pages: int = 1
    expect_text: bool = True
    expect_encrypted: bool = False
    min_layout_elements: int = 0
    min_text_quality: float = 0.0


# ---------------------------------------------------------------------------
# Define expectations for each benchmark PDF
# ---------------------------------------------------------------------------

BENCHMARKS: list[BenchmarkExpectation] = [
    BenchmarkExpectation(
        name="sbi_statement_native",
        category="native",
        file_path=str(BENCHMARK_DIR / "native" / "sbi_statement_native.pdf"),
        expected_pipeline=PipelineType.NATIVE,
        expect_text=True,
        min_layout_elements=1,
        min_text_quality=0.5,
    ),
    BenchmarkExpectation(
        name="scanned_doc",
        category="scanned",
        file_path=str(BENCHMARK_DIR / "scanned" / "scanned_doc.pdf"),
        expected_pipeline=PipelineType.OCR,
        expect_text=False,
    ),
    BenchmarkExpectation(
        name="hdfc_hybrid",
        category="hybrid",
        file_path=str(BENCHMARK_DIR / "hybrid" / "hdfc_hybrid.pdf"),
        expected_pipeline=PipelineType.NATIVE,
        expect_text=True,
        min_layout_elements=1,
        min_text_quality=0.3,
    ),
    BenchmarkExpectation(
        name="empty",
        category="broken",
        file_path=str(BENCHMARK_DIR / "broken" / "empty.pdf"),
        expected_pipeline=PipelineType.OCR,
        expect_text=False,
    ),
]


@dataclasses.dataclass
class BenchmarkResult:
    """Result of running a single benchmark."""

    name: str
    category: str
    passed: bool
    diagnostics: DiagnosticReport | None = None
    layout_count: int = 0
    failure_reasons: list[str] = dataclasses.field(default_factory=list)


def run_benchmark(expectation: BenchmarkExpectation) -> BenchmarkResult:
    """Run diagnostics on a benchmark PDF and compare against expectations.

    Args:
        expectation: The expected results for this benchmark.

    Returns:
        A ``BenchmarkResult`` indicating pass/fail.
    """
    failures: list[str] = []

    try:
        analyzer = DocumentAnalyzer(Path(expectation.file_path))
        report = analyzer.analyze()
    except Exception as exc:
        failures.append(f"Diagnostics failed: {exc}")
        return BenchmarkResult(
            name=expectation.name,
            category=expectation.category,
            passed=False,
            failure_reasons=failures,
        )

    # Pipeline type
    if report.recommended_pipeline != expectation.expected_pipeline:
        failures.append(
            f"Pipeline: expected {expectation.expected_pipeline.value}, "
            f"got {report.recommended_pipeline.value}"
        )

    # Page count
    if report.page_count < expectation.min_pages:
        failures.append(f"Pages: expected >= {expectation.min_pages}, got {report.page_count}")

    # Text presence
    if report.has_native_text != expectation.expect_text:
        failures.append(f"Text: expected {expectation.expect_text}, got {report.has_native_text}")

    # Encrypted
    if report.is_encrypted != expectation.expect_encrypted:
        failures.append(
            f"Encrypted: expected {expectation.expect_encrypted}, "
            f"got {report.is_encrypted}"
        )

    # Text quality
    if expectation.min_text_quality > 0 and report.text_quality_report is not None:
        if report.text_quality_report.overall_score < expectation.min_text_quality:
            failures.append(
                f"Quality: expected >= {expectation.min_text_quality}, "
                f"got {report.text_quality_report.overall_score:.4f}"
            )

    # Layout analysis
    layout_count = 0
    try:
        parser = PDFParser(Path(expectation.file_path))
        document = parser.parse()
        layout_results = LayoutAnalyzer.analyze(document)
        layout_count = sum(len(lr.elements) for lr in layout_results)
        if layout_count < expectation.min_layout_elements:
            failures.append(
                f"Layout: expected >= {expectation.min_layout_elements} elements, "
                f"got {layout_count}"
            )
    except Exception as exc:
        if expectation.min_layout_elements > 0:
            failures.append(f"Layout analysis failed: {exc}")

    return BenchmarkResult(
        name=expectation.name,
        category=expectation.category,
        passed=len(failures) == 0,
        diagnostics=report,
        layout_count=layout_count,
        failure_reasons=failures,
    )


def run_all() -> list[BenchmarkResult]:
    """Run all benchmarks and return results.

    Returns:
        A list of ``BenchmarkResult`` for every benchmark.
    """
    return [run_benchmark(b) for b in BENCHMARKS]


def print_results(results: list[BenchmarkResult]) -> None:
    """Pretty-print benchmark results.

    Args:
        results: Benchmark results to display.
    """
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    print(f"\n{'='*60}")
    print(f"  Regression Results: {passed}/{total} passed")
    print(f"{'='*60}")

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.category:8s} | {r.name}")
        if not r.passed:
            for reason in r.failure_reasons:
                print(f"          -> {reason}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    results = run_all()
    print_results(results)
    failed = [r for r in results if not r.passed]
    raise SystemExit(1 if failed else 0)
