"""Tests for bank profilers and registry."""
from __future__ import annotations

import datetime

from privacy_firewall.bank_profiler import (
    AxisProfiler,
    BankName,
    BankProfilerRegistry,
    GenericProfiler,
    HDFCProfiler,
    ICICIProfiler,
    SBIProfiler,
)
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox


def _doc(blocks: list[TextBlock], pages: int = 1) -> Document:
    return Document(
        pages=[Page(page_number=i + 1, width=600, height=800, blocks=blocks) for i in range(pages)],
    )


def _tb(text: str) -> TextBlock:
    return TextBlock(
        block_id="b1",
        bbox=BoundingBox(x0=0, y0=0, x1=100, y1=10),
        page_number=1,
        confidence=1.0,
        text=text,
    )


# ---------------------------------------------------------------------------
# Individual profilers
# ---------------------------------------------------------------------------


class TestSBIProfiler:
    def test_identifies_sbi(self) -> None:
        doc = _doc([_tb("State Bank of India\nSBIN0012345\nAccount: 12345678901")])
        p = SBIProfiler().profile(doc)
        assert p.bank_name == BankName.SBI
        assert p.confidence >= 0.8
        assert p.ifsc_code == "SBIN0012345"

    def test_wrong_ifsc_returns_zero(self) -> None:
        doc = _doc([_tb("HDFC0001234 some text")])
        p = SBIProfiler().profile(doc)
        assert p.confidence == 0.0

    def test_sbi_no_ifsc(self) -> None:
        doc = _doc([_tb("State Bank of India account statement")])
        p = SBIProfiler().profile(doc)
        assert p.confidence == 0.3  # name alias only, no IFSC


class TestHDFCProfiler:
    def test_identifies_hdfc(self) -> None:
        doc = _doc([_tb("HDFC Bank\nHDFC0001234\nAccount: 12345678901234")])
        p = HDFCProfiler().profile(doc)
        assert p.bank_name == BankName.HDFC
        assert p.confidence >= 0.8

    def test_wrong_ifsc_returns_zero(self) -> None:
        doc = _doc([_tb("SBIN0012345 some text")])
        p = HDFCProfiler().profile(doc)
        assert p.confidence == 0.0


class TestICICIProfiler:
    def test_identifies_icici(self) -> None:
        doc = _doc([_tb("ICICI Bank\nICIC0001234")])
        p = ICICIProfiler().profile(doc)
        assert p.bank_name == BankName.ICICI
        assert p.confidence >= 0.8

    def test_wrong_ifsc_returns_zero(self) -> None:
        doc = _doc([_tb("SBIN0012345")])
        p = ICICIProfiler().profile(doc)
        assert p.confidence == 0.0


class TestAxisProfiler:
    def test_identifies_axis_utib(self) -> None:
        doc = _doc([_tb("Axis Bank\nUTIB0001234")])
        p = AxisProfiler().profile(doc)
        assert p.bank_name == BankName.AXIS
        assert p.confidence >= 0.8

    def test_identifies_axis_axis_ifsc(self) -> None:
        doc = _doc([_tb("Axis Bank\nAXIS0001234")])
        p = AxisProfiler().profile(doc)
        assert p.bank_name == BankName.AXIS
        assert p.confidence >= 0.8


class TestGenericProfiler:
    def test_no_ifsc_low_confidence(self) -> None:
        doc = _doc([_tb("Bank statement")])
        p = GenericProfiler().profile(doc)
        assert p.bank_name == BankName.GENERIC
        assert p.confidence == 0.1

    def test_with_ifsc(self) -> None:
        doc = _doc([_tb("SBIN0012345 Statement")])
        p = GenericProfiler().profile(doc)
        assert p.confidence >= 0.2

    def test_full_metadata(self) -> None:
        doc = _doc([_tb("SBIN0012345\nPeriod: 01 Apr 2024 to 31 Mar 2025\nName: John")])
        p = GenericProfiler().profile(doc)
        assert p.ifsc_code == "SBIN0012345"
        assert p.statement_start == datetime.date(2024, 4, 1)
        assert p.statement_end == datetime.date(2025, 3, 31)
        assert p.account_holder == "John"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestBankProfilerRegistry:
    def test_empty_returns_generic_zero_confidence(self) -> None:
        r = BankProfilerRegistry()
        p = r.profile(_doc([_tb("text")]))
        assert p.bank_name == BankName.GENERIC
        assert p.confidence == 0.0

    def test_register_and_pick_highest(self) -> None:
        r = BankProfilerRegistry()
        r.register(SBIProfiler)
        r.register(HDFCProfiler)
        p = r.profile(_doc([_tb("State Bank of India\nSBIN0012345")]))
        assert p.bank_name == BankName.SBI

    def test_picks_hdfc_when_hdfc_document(self) -> None:
        r = BankProfilerRegistry()
        r.register(SBIProfiler)
        r.register(HDFCProfiler)
        p = r.profile(_doc([_tb("HDFC Bank\nHDFC0001234\nAccount: 12345678901234")]))
        assert p.bank_name == BankName.HDFC

    def test_names_property(self) -> None:
        r = BankProfilerRegistry()
        r.register(SBIProfiler)
        r.register(HDFCProfiler)
        assert set(r.names) == {"sbi", "hdfc"}
