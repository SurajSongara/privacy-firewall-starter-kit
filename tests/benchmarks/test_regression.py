"""Regression tests — run benchmarks and verify diagnostics + recall."""
from __future__ import annotations

import pytest

from benchmarks.generate_benchmarks import generate_all
from benchmarks.runner import BenchmarkExpectation, BENCHMARKS, run_benchmark


@pytest.fixture(scope="session", autouse=True)
def _generate_benchmarks() -> None:
    """Generate benchmark PDFs once before the test session."""
    generate_all()


class TestBenchmarkDiagnostics:
    """Run diagnostics on each benchmark PDF and verify expectations."""

    @pytest.mark.parametrize(
        "benchmark",
        BENCHMARKS,
        ids=[b.name for b in BENCHMARKS],
    )
    def test_benchmark(self, benchmark: BenchmarkExpectation) -> None:
        result = run_benchmark(benchmark)
        assert result.passed, (
            f"Benchmark {result.name} failed:\n"
            + "\n".join(f"  - {r}" for r in result.failure_reasons)
        )


class TestRecallNative:
    """Verify PII detection recall on a native PDF."""

    def test_native_pii_detected(self) -> None:
        """Scan a native PDF with detectors and verify PII is found."""
        from pathlib import Path

        from privacy_firewall.detectors import (
            AadhaarDetector,
            DetectorRegistry,
            EmailDetector,
            PANDetector,
            PhoneDetector,
            UpiDetector,
        )
        from privacy_firewall.parsers.pdf_parser import PDFParser

        pdf_path = Path("benchmarks/native/sbi_statement_native.pdf")
        parser = PDFParser(pdf_path)
        doc = parser.parse()

        registry = DetectorRegistry()
        registry.register(PANDetector())
        registry.register(EmailDetector())
        registry.register(PhoneDetector())
        registry.register(AadhaarDetector())
        registry.register(UpiDetector())

        result = registry.run_all(doc)
        detections = result.detections

        types_found = {d.detection_type for d in detections}

        assert "PAN" in types_found, f"PAN not detected in native PDF. Types: {types_found}"
        assert "EMAIL" in types_found, f"Email not detected in native PDF. Types: {types_found}"
        assert "PHONE" in types_found, f"Phone not detected in native PDF. Types: {types_found}"


class TestRecallOCR:
    """Verify behaviour on scanned/broken PDFs (should find little or nothing)."""

    def test_empty_pdf_no_pii(self) -> None:
        """An empty PDF should yield zero detections."""
        from pathlib import Path

        from privacy_firewall.detectors import (
            DetectorRegistry,
            EmailDetector,
            PANDetector,
            PhoneDetector,
        )
        from privacy_firewall.parsers.pdf_parser import PDFParser

        pdf_path = Path("benchmarks/broken/empty.pdf")
        parser = PDFParser(pdf_path)
        doc = parser.parse()

        registry = DetectorRegistry()
        registry.register(PANDetector())
        registry.register(EmailDetector())
        registry.register(PhoneDetector())

        result = registry.run_all(doc)
        assert len(result.detections) == 0
