"""Tests for the PipelineSelector."""
from __future__ import annotations

from privacy_firewall.diagnostics import PipelineSelector, PipelineType


class TestPipelineSelect:
    def test_encrypted_returns_ocr(self) -> None:
        assert PipelineSelector.select(is_encrypted=True) == PipelineType.OCR

    def test_zero_pages_returns_ocr(self) -> None:
        assert PipelineSelector.select(page_count=0) == PipelineType.OCR

    def test_scanned_returns_ocr(self) -> None:
        assert PipelineSelector.select(
            has_native_text=True, text_quality_score=0.9, estimated_scanned=True,
        ) == PipelineType.OCR

    def test_no_text_returns_ocr(self) -> None:
        assert PipelineSelector.select(has_native_text=False) == PipelineType.OCR

    def test_low_quality_returns_ocr(self) -> None:
        assert PipelineSelector.select(
            has_native_text=True, text_quality_score=0.1,
        ) == PipelineType.OCR

    def test_medium_quality_returns_hybrid(self) -> None:
        assert PipelineSelector.select(
            has_native_text=True, text_quality_score=0.5,
        ) == PipelineType.HYBRID

    def test_high_quality_returns_native(self) -> None:
        assert PipelineSelector.select(
            has_native_text=True, text_quality_score=0.9,
        ) == PipelineType.NATIVE

    def test_default_returns_native(self) -> None:
        assert PipelineSelector.select() == PipelineType.NATIVE

    def test_quality_just_below_low(self) -> None:
        score = PipelineSelector.LOW_QUALITY_THRESHOLD - 0.001
        assert PipelineSelector.select(
            has_native_text=True, text_quality_score=score,
        ) == PipelineType.OCR

    def test_quality_at_low_is_hybrid(self) -> None:
        score = PipelineSelector.LOW_QUALITY_THRESHOLD
        assert PipelineSelector.select(
            has_native_text=True, text_quality_score=score,
        ) == PipelineType.HYBRID

    def test_quality_at_medium_is_native(self) -> None:
        score = PipelineSelector.MEDIUM_QUALITY_THRESHOLD
        assert PipelineSelector.select(
            has_native_text=True, text_quality_score=score,
        ) == PipelineType.NATIVE

    def test_quality_just_over_medium(self) -> None:
        score = PipelineSelector.MEDIUM_QUALITY_THRESHOLD + 0.01
        assert PipelineSelector.select(
            has_native_text=True, text_quality_score=score,
        ) == PipelineType.NATIVE

    def test_encrypted_takes_priority_over_quality(self) -> None:
        assert PipelineSelector.select(
            is_encrypted=True, has_native_text=True, text_quality_score=0.9,
        ) == PipelineType.OCR

    def test_encrypted_takes_priority_over_scanned(self) -> None:
        assert PipelineSelector.select(
            is_encrypted=True, estimated_scanned=False,
        ) == PipelineType.OCR


class TestEstimateScanned:
    def test_zero_pages(self) -> None:
        assert PipelineSelector.estimate_scanned(page_count=0) is False

    def test_high_images(self) -> None:
        factor = PipelineSelector.SCANNED_IMAGE_THRESHOLD
        assert PipelineSelector.estimate_scanned(
            page_count=1, image_count=factor + 1, text_quality_score=1.0,
        ) is True

    def test_exactly_at_threshold_not_scanned(self) -> None:
        factor = PipelineSelector.SCANNED_IMAGE_THRESHOLD
        assert PipelineSelector.estimate_scanned(
            page_count=1, image_count=factor, text_quality_score=1.0,
        ) is False

    def test_quality_below_threshold_with_images(self) -> None:
        score = PipelineSelector.SCANNED_QUALITY_THRESHOLD - 0.01
        assert PipelineSelector.estimate_scanned(
            page_count=1, image_count=1, text_quality_score=score,
        ) is True

    def test_quality_at_threshold_not_scanned(self) -> None:
        score = PipelineSelector.SCANNED_QUALITY_THRESHOLD
        assert PipelineSelector.estimate_scanned(
            page_count=1, image_count=1, text_quality_score=score,
        ) is False

    def test_no_images_not_scanned(self) -> None:
        assert PipelineSelector.estimate_scanned(
            page_count=5, image_count=0, text_quality_score=0.0,
        ) is False

    def test_defaults_not_scanned(self) -> None:
        assert PipelineSelector.estimate_scanned() is False
