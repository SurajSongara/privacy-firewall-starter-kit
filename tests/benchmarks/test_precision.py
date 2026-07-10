"""Precision/recall regression tests against the synthetic dataset baseline."""

from __future__ import annotations

import pytest

from benchmarks.precision import BASELINE_PATH, TypeMetrics, evaluate, load_baseline

TOLERANCE = 0.02
"""Allowed absolute drop in precision/recall before the test fails."""


@pytest.fixture(scope="module")
def metrics() -> dict[str, TypeMetrics]:
    """Evaluate the synthetic dataset once for all tests in this module."""
    return evaluate()


class TestPrecisionBaseline:
    def test_baseline_exists(self) -> None:
        assert BASELINE_PATH.exists(), (
            "Missing precision baseline. Generate it with: python -m benchmarks.precision --update"
        )

    def test_no_metric_regression(self, metrics: dict[str, TypeMetrics]) -> None:
        baseline = load_baseline()
        failures: list[str] = []
        for dtype, expected in baseline.items():
            current = metrics[dtype]
            if current.precision < expected["precision"] - TOLERANCE:
                failures.append(
                    f"{dtype} precision {current.precision:.2%} < baseline "
                    f"{expected['precision']:.2%} (FPs: {current.fp_examples})"
                )
            if current.recall < expected["recall"] - TOLERANCE:
                failures.append(
                    f"{dtype} recall {current.recall:.2%} < baseline "
                    f"{expected['recall']:.2%} (FNs: {current.fn_examples})"
                )
        assert not failures, "Metric regressions:\n" + "\n".join(f"  - {f}" for f in failures)

    def test_all_types_evaluated(self, metrics: dict[str, TypeMetrics]) -> None:
        # Every detector type must have at least one labeled example,
        # otherwise its metrics are vacuously perfect.
        starved = [t for t, m in metrics.items() if m.tp + m.fn == 0]
        assert not starved, f"No labeled examples for: {starved}"
