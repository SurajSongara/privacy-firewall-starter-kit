"""Text quality analysis using multiple heuristic measurements."""
from __future__ import annotations

import re

from privacy_firewall.diagnostics.models import TextQualityReport

_REPLACEMENT_CHAR = "\ufffd"
_PRINTABLE_RE = re.compile(r"[^\x00-\x1f\x7f-\x9f\ufffd]")
_WORD_SPLIT_RE = re.compile(r"\S+")
_WHITESPACE_RE = re.compile(r"\s")


class TextQualityAnalyzer:
    """Evaluates text quality using a suite of heuristic measurements.

    Each heuristic contributes a normalised component (0.0 = worst,
    1.0 = best) which is combined into a weighted overall score.
    """

    WEIGHTS = {
        "printable": 0.30,
        "replace": 0.20,
        "fragmentation": 0.15,
        "token": 0.20,
        "whitespace": 0.15,
    }
    """Relative weights for each heuristic component."""

    FRAGMENT_CHAR_THRESHOLD = 3
    """Words shorter than this (in characters) are considered fragments."""

    LONG_TOKEN_THRESHOLD = 50
    """Tokens longer than this are penalised."""

    REPLACE_PENALTY_FACTOR = 5.0
    """Multiplier for replacement-character penalty."""

    LONG_TOKEN_PENALTY_FACTOR = 10.0
    """Multiplier for long-token penalty."""

    MIN_WHITESPACE_RATIO = 0.02
    """Below this whitespace fraction the text is considered dense/no spaces."""

    MAX_WHITESPACE_RATIO = 0.50
    """Above this whitespace fraction text is mostly whitespace."""

    @classmethod
    def analyze(cls, text: str) -> TextQualityReport:
        """Run all heuristic measurements and produce a quality report.

        Args:
            text: The text content to analyse.

        Returns:
            A ``TextQualityReport`` with component scores and reasons.
        """
        if not text.strip():
            return TextQualityReport(
                overall_score=0.0,
                printable_ratio=0.0,
                replace_penalty=0.0,
                fragmentation_score=0.0,
                token_quality=0.0,
                whitespace_ratio=0.0,
                reasons=["empty or blank text"],
            )

        char_count = len(text)
        reasons: list[str] = []

        printable_ratio = cls._score_printable_ratio(text, char_count, reasons)
        replace_penalty = cls._score_replace_penalty(text, char_count, reasons)
        fragmentation_score = cls._score_fragmentation(text, reasons)
        token_quality = cls._score_token_quality(text, reasons)
        whitespace_ratio = cls._score_whitespace(text, char_count, reasons)

        overall = (
            printable_ratio * cls.WEIGHTS["printable"]
            + replace_penalty * cls.WEIGHTS["replace"]
            + fragmentation_score * cls.WEIGHTS["fragmentation"]
            + token_quality * cls.WEIGHTS["token"]
            + whitespace_ratio * cls.WEIGHTS["whitespace"]
        )
        overall = max(0.0, min(1.0, overall))

        return TextQualityReport(
            overall_score=round(overall, 4),
            printable_ratio=round(printable_ratio, 4),
            replace_penalty=round(replace_penalty, 4),
            fragmentation_score=round(fragmentation_score, 4),
            token_quality=round(token_quality, 4),
            whitespace_ratio=round(whitespace_ratio, 4),
            reasons=sorted(reasons),
        )

    @staticmethod
    def _score_printable_ratio(text: str, char_count: int, reasons: list[str]) -> float:
        """Printable-character ratio heuristic."""
        printable_matches = _PRINTABLE_RE.findall(text)
        printable_count = len(printable_matches)
        ratio = printable_count / max(char_count, 1)
        if ratio < 0.7:
            reasons.append("low printable character ratio")
        return ratio

    @staticmethod
    def _score_replace_penalty(text: str, char_count: int, reasons: list[str]) -> float:
        """Replacement-character penalty heuristic."""
        replace_count = text.count(_REPLACEMENT_CHAR)
        factor = TextQualityAnalyzer.REPLACE_PENALTY_FACTOR
        penalty = 1.0 - (replace_count / max(char_count, 1)) * factor
        penalty = max(0.0, penalty)
        if penalty < 0.7:
            reasons.append("high replacement character count")
        return penalty

    @staticmethod
    def _score_fragmentation(text: str, reasons: list[str]) -> float:
        """Short-word fragmentation heuristic."""
        words = _WORD_SPLIT_RE.findall(text)
        if not words:
            return 0.0
        short_words = sum(1 for w in words if len(w) < TextQualityAnalyzer.FRAGMENT_CHAR_THRESHOLD)
        fragmentation = 1.0 - (short_words / len(words)) * 2
        fragmentation = max(0.0, fragmentation)
        if fragmentation < 0.6:
            reasons.append("fragmented text (many short words)")
        return fragmentation

    @staticmethod
    def _score_token_quality(text: str, reasons: list[str]) -> float:
        """Long-token penalty heuristic."""
        words = _WORD_SPLIT_RE.findall(text)
        if not words:
            return 0.0
        threshold = TextQualityAnalyzer.LONG_TOKEN_THRESHOLD
        long_tokens = sum(1 for w in words if len(w) > threshold)
        tf = TextQualityAnalyzer.LONG_TOKEN_PENALTY_FACTOR
        quality = 1.0 - (long_tokens / len(words)) * tf
        quality = max(0.0, quality)
        if quality < 0.6:
            reasons.append("very long unbroken tokens detected")
        return quality

    @staticmethod
    def _score_whitespace(text: str, char_count: int, reasons: list[str]) -> float:
        """Whitespace ratio heuristic."""
        ws_count = len(_WHITESPACE_RE.findall(text))
        ratio = ws_count / max(char_count, 1)
        if ratio < TextQualityAnalyzer.MIN_WHITESPACE_RATIO:
            reasons.append("very little whitespace (dense text)")
            return 0.0
        if ratio > TextQualityAnalyzer.MAX_WHITESPACE_RATIO:
            reasons.append("mostly whitespace")
            return 0.0
        return 1.0
