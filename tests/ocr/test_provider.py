"""Tests for the OCRProvider abstract interface."""
from __future__ import annotations

from pathlib import Path

import pytest

from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox
from privacy_firewall.ocr import OCRProvider, OCRProviderRegistry


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
