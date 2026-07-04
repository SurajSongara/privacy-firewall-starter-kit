"""Tests for the TextQualityAnalyzer."""
from __future__ import annotations

import pytest

from privacy_firewall.diagnostics import TextQualityAnalyzer


class TestTextQualityAnalyzer:
    def test_empty_text(self) -> None:
        r = TextQualityAnalyzer.analyze("")
        assert r.overall_score == 0.0
        assert "empty or blank text" in r.reasons

    def test_blank_text(self) -> None:
        r = TextQualityAnalyzer.analyze("   ")
        assert r.overall_score == 0.0
        assert "empty or blank text" in r.reasons

    def test_perfect_text(self) -> None:
        text = "Hello world. This is a normal sentence with good quality text."
        r = TextQualityAnalyzer.analyze(text)
        assert r.overall_score > 0.9
        assert r.reasons == []

    def test_printable_ratio_low(self) -> None:
        text = "\x00\x00\x00\x00" + "hello"
        r = TextQualityAnalyzer.analyze(text)
        assert r.printable_ratio < 0.7
        assert "low printable character ratio" in r.reasons

    def test_replacement_char_penalty(self) -> None:
        r = TextQualityAnalyzer.analyze("\ufffd" * 50)
        assert r.replace_penalty < 0.7
        assert "high replacement character count" in r.reasons

    def test_fragmentation(self) -> None:
        text = "a b c d e f g h i j k l m n o p"
        r = TextQualityAnalyzer.analyze(text)
        assert r.fragmentation_score < 0.6
        assert any("fragmented text" in reason for reason in r.reasons)

    def test_token_quality_long(self) -> None:
        text = "A" * 60 + " B" * 5
        r = TextQualityAnalyzer.analyze(text)
        assert r.token_quality < 0.6
        assert any("long unbroken tokens" in reason for reason in r.reasons)

    def test_whitespace_too_little(self) -> None:
        r = TextQualityAnalyzer.analyze("hello" + "\x00" * 20 + "world")
        assert r.whitespace_ratio == 0.0
        assert any("whitespace" in reason for reason in r.reasons)

    def test_whitespace_too_much(self) -> None:
        r = TextQualityAnalyzer.analyze("   " * 100 + "hello")
        assert r.whitespace_ratio == 0.0
        assert "mostly whitespace" in r.reasons

    def test_whitespace_normal(self) -> None:
        r = TextQualityAnalyzer.analyze("Hello world. Good text here.")
        assert r.whitespace_ratio == 1.0
        assert "whitespace" not in " ".join(r.reasons).lower()

    def test_report_frozen(self) -> None:
        r = TextQualityAnalyzer.analyze("hello")
        with pytest.raises((TypeError, ValueError)):
            r.overall_score = 0.0  # type: ignore[misc]

    def test_overall_score_bounded(self) -> None:
        r = TextQualityAnalyzer.analyze("\x00" * 1000 + "hi")
        assert 0.0 <= r.overall_score <= 1.0

    def test_high_quality_no_reasons(self) -> None:
        text = "The quick brown fox jumps over the lazy dog near the river."
        r = TextQualityAnalyzer.analyze(text)
        assert r.overall_score > 0.85

    def test_moderate_scores(self) -> None:
        text = "\x00\x00hello world\x00\x00"
        r = TextQualityAnalyzer.analyze(text)
        assert 0.0 <= r.overall_score <= 1.0
        assert all(
            0.0 <= getattr(r, attr) <= 1.0
            for attr in [
                "printable_ratio",
                "replace_penalty",
                "fragmentation_score",
                "token_quality",
                "whitespace_ratio",
            ]
        )
