"""Tests for the OCRProvider abstract interface."""
from __future__ import annotations

from pathlib import Path

import pytest

from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox
from privacy_firewall.ocr import (
    OCR_ENGINE_ENV_VAR,
    OCRProvider,
    OCRProviderRegistry,
    _resolve_default,
)


class _DummyProvider(OCRProvider):
    """A minimal concrete provider for testing the interface."""

    name = "dummy"

    def process(self, path: str | Path) -> Document:
        return self._make_doc()

    def process_bytes(self, data: bytes) -> Document:
        return self._make_doc()

    @staticmethod
    def _make_doc() -> Document:
        return Document(
            pages=[
                Page(
                    page_number=1,
                    width=600,
                    height=800,
                    blocks=[
                        TextBlock(
                            block_id="b1",
                            bbox=BoundingBox(x0=10, y0=10, x1=100, y1=30),
                            page_number=1,
                            confidence=0.95,
                            text="Hello from dummy OCR",
                        ),
                    ],
                ),
            ],
        )


class TestOCRProviderInterface:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            OCRProvider()  # type: ignore[abstract]

    def test_concrete_provider_has_name(self) -> None:
        p = _DummyProvider()
        assert p.name == "dummy"

    def test_process_returns_document(self) -> None:
        p = _DummyProvider()
        doc = p.process("/fake/path.pdf")
        assert isinstance(doc, Document)

    def test_process_bytes_returns_document(self) -> None:
        p = _DummyProvider()
        doc = p.process_bytes(b"fake pdf content")
        assert isinstance(doc, Document)

    def test_process_contains_text_blocks(self) -> None:
        p = _DummyProvider()
        doc = p.process("/fake/path.pdf")
        assert len(doc.pages) == 1
        assert len(doc.pages[0].blocks) == 1
        block = doc.pages[0].blocks[0]
        assert isinstance(block, TextBlock)
        assert "dummy OCR" in block.text
        assert block.confidence == 0.95


class TestOCRProviderRegistry:
    def test_empty(self) -> None:
        r = OCRProviderRegistry()
        assert r.names == []
        assert r.default_name is None
        assert r.get_default() is None

    def test_register_and_get(self) -> None:
        r = OCRProviderRegistry()
        r.register(_DummyProvider)
        assert r.names == ["dummy"]
        assert r.get("dummy") is _DummyProvider

    def test_get_missing(self) -> None:
        r = OCRProviderRegistry()
        assert r.get("nonexistent") is None

    def test_register_sets_default(self) -> None:
        r = OCRProviderRegistry()
        r.register(_DummyProvider)
        assert r.default_name == "dummy"
        assert r.get_default() is _DummyProvider

    def test_register_explicit_default(self) -> None:
        r = OCRProviderRegistry()
        r.register(_DummyProvider, default=True)
        assert r.default_name == "dummy"

    def test_set_default_name(self) -> None:
        r = OCRProviderRegistry()
        r.register(_DummyProvider)
        r.default_name = "dummy"
        assert r.default_name == "dummy"

    def test_set_unknown_default_raises(self) -> None:
        r = OCRProviderRegistry()
        with pytest.raises(KeyError, match="Unknown OCR provider"):
            r.default_name = "missing"

    def test_register_overwrites(self) -> None:
        r = OCRProviderRegistry()

        class _V2(_DummyProvider):
            name = "dummy"

        r.register(_DummyProvider)
        r.register(_V2)
        assert r.get("dummy") is _V2


class _RapidDummy(_DummyProvider):
    name = "rapidocr"


class _TesseractDummy(_DummyProvider):
    name = "tesseract"


class _PaddleDummy(_DummyProvider):
    name = "paddleocr"


class TestDefaultResolution:
    """The default engine is deterministic: env var, then preference order."""

    def test_prefers_rapidocr_over_tesseract(self) -> None:
        r = OCRProviderRegistry()
        r.register(_TesseractDummy)
        r.register(_RapidDummy)
        _resolve_default(r, None)
        assert r.default_name == "rapidocr"

    def test_registration_order_does_not_matter(self) -> None:
        r = OCRProviderRegistry()
        r.register(_RapidDummy)
        r.register(_TesseractDummy)
        _resolve_default(r, None)
        assert r.default_name == "rapidocr"

    def test_falls_back_to_tesseract_then_paddle(self) -> None:
        r = OCRProviderRegistry()
        r.register(_PaddleDummy)
        r.register(_TesseractDummy)
        _resolve_default(r, None)
        assert r.default_name == "tesseract"

    def test_env_var_overrides_preference(self) -> None:
        r = OCRProviderRegistry()
        r.register(_RapidDummy)
        r.register(_TesseractDummy)
        _resolve_default(r, "tesseract")
        assert r.default_name == "tesseract"

    def test_env_var_is_case_insensitive(self) -> None:
        r = OCRProviderRegistry()
        r.register(_TesseractDummy)
        _resolve_default(r, "  Tesseract ")
        assert r.default_name == "tesseract"

    def test_unknown_env_var_warns_and_falls_back(self) -> None:
        r = OCRProviderRegistry()
        r.register(_TesseractDummy)
        with pytest.warns(UserWarning, match=OCR_ENGINE_ENV_VAR):
            _resolve_default(r, "nonexistent")
        assert r.default_name == "tesseract"

    def test_unlisted_engine_keeps_registration_default(self) -> None:
        # A third-party engine outside the preference list stays default
        # when nothing in the preference list is registered.
        r = OCRProviderRegistry()
        r.register(_DummyProvider)
        _resolve_default(r, None)
        assert r.default_name == "dummy"

    def test_empty_registry_is_a_no_op(self) -> None:
        r = OCRProviderRegistry()
        _resolve_default(r, None)
        assert r.default_name is None

    def test_skips_registered_but_unavailable_engine(self) -> None:
        # Adapters lazy-import their backend, so registration alone does
        # not prove the engine can run; the preference scan must skip it.
        class _RapidMissing(_RapidDummy):
            @classmethod
            def is_available(cls) -> bool:
                return False

        r = OCRProviderRegistry()
        r.register(_RapidMissing)
        r.register(_TesseractDummy)
        _resolve_default(r, None)
        assert r.default_name == "tesseract"

    def test_env_pin_honoured_even_if_unavailable(self) -> None:
        # An explicit pin should surface the adapter's install-hint
        # ImportError at run time rather than silently falling back.
        class _PaddleMissing(_PaddleDummy):
            @classmethod
            def is_available(cls) -> bool:
                return False

        r = OCRProviderRegistry()
        r.register(_PaddleMissing)
        r.register(_TesseractDummy)
        _resolve_default(r, "paddleocr")
        assert r.default_name == "paddleocr"
