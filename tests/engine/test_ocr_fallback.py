"""Tests for OCR engine fallback when the default engine fails at runtime."""

from pathlib import Path

import pytest

import privacy_firewall.ocr as ocr_module
from privacy_firewall.engine.ocr_pipeline import _run_ocr
from privacy_firewall.models.document import Document
from privacy_firewall.ocr.registry import OCRProviderRegistry

SENTINEL_DOC = Document(pages=[])


class BrokenAdapter:
    """Imports fine but explodes at runtime (like Tesseract w/o tessdata)."""

    name = "broken"

    def process(self, pdf_path: Path) -> Document:
        msg = "Failed to init API, possibly an invalid tessdata path"
        raise RuntimeError(msg)


class WorkingAdapter:
    name = "working"

    def process(self, pdf_path: Path) -> Document:
        return SENTINEL_DOC


class AlsoBrokenAdapter:
    name = "also-broken"

    def process(self, pdf_path: Path) -> Document:
        raise ImportError("paddlepaddle is not installed")


def _patch_registry(monkeypatch: pytest.MonkeyPatch, *adapters: type) -> None:
    registry = OCRProviderRegistry()
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]
    monkeypatch.setattr(ocr_module, "_registry", registry)


class TestOCRFallback:
    def test_falls_back_to_next_engine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_registry(monkeypatch, BrokenAdapter, WorkingAdapter)
        assert _run_ocr(Path("x.pdf")) is SENTINEL_DOC

    def test_default_engine_tried_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        registry = OCRProviderRegistry()
        registry.register(BrokenAdapter)  # type: ignore[arg-type]
        registry.register(WorkingAdapter, default=True)  # type: ignore[arg-type]
        monkeypatch.setattr(ocr_module, "_registry", registry)
        assert _run_ocr(Path("x.pdf")) is SENTINEL_DOC

    def test_all_engines_failing_raises_with_details(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_registry(monkeypatch, BrokenAdapter, AlsoBrokenAdapter)
        with pytest.raises(RuntimeError, match="All OCR engines failed") as excinfo:
            _run_ocr(Path("x.pdf"))
        assert "broken: " in str(excinfo.value)
        assert "also-broken: " in str(excinfo.value)

    def test_named_engine_does_not_fall_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_registry(monkeypatch, BrokenAdapter, WorkingAdapter)
        with pytest.raises(RuntimeError, match="tessdata"):
            _run_ocr(Path("x.pdf"), provider="broken")
