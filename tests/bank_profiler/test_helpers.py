"""Tests for shared bank-profiler helpers."""
from __future__ import annotations

import datetime
import re

from privacy_firewall.bank_profiler._helpers import (
    extract_all_text,
    find_account_holder,
    find_account_number,
    find_ifsc,
    find_statement_period,
)
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox


def _text(text: str, page_num: int = 1) -> TextBlock:
    return TextBlock(
        block_id=f"b{page_num}",
        bbox=BoundingBox(x0=0, y0=0, x1=100, y1=10),
        page_number=page_num,
        confidence=1.0,
        text=text,
    )


class TestExtractAllText:
    def test_single_page(self) -> None:
        doc = Document(pages=[Page(page_number=1, width=600, height=800, blocks=[
            _text("Hello"),
            _text("World"),
        ])])
        assert extract_all_text(doc) == "Hello\nWorld"

    def test_multi_page(self) -> None:
        doc = Document(pages=[
            Page(page_number=1, width=600, height=800, blocks=[_text("Page1")]),
            Page(page_number=2, width=600, height=800, blocks=[_text("Page2")]),
        ])
        result = extract_all_text(doc)
        assert "Page1" in result
        assert "Page2" in result


class TestFindIFSC:
    def test_valid(self) -> None:
        assert find_ifsc("IFSC: SBIN0012345") == "SBIN0012345"

    def test_none(self) -> None:
        assert find_ifsc("No IFSC here") is None

    def test_multiple_returns_first(self) -> None:
        assert find_ifsc("SBIN0012345 and HDFC0001234") == "SBIN0012345"


class TestFindAccountNumber:
    def test_matches_pattern(self) -> None:
        pats = [re.compile(r"\b\d{11}\b")]
        assert find_account_number("Acct: 12345678901", pats) == "12345678901"

    def test_no_match(self) -> None:
        pats = [re.compile(r"\b\d{11}\b")]
        assert find_account_number("Acct: 42", pats) is None


class TestFindStatementPeriod:
    def test_period_label(self) -> None:
        text = "Statement Period: 01 Apr 2024 to 31 Mar 2025"
        start, end = find_statement_period(text)
        assert start == datetime.date(2024, 4, 1)
        assert end == datetime.date(2025, 3, 31)

    def test_from_to(self) -> None:
        text = "from 01 April 2024 to 31 March 2025"
        start, end = find_statement_period(text)
        assert start == datetime.date(2024, 4, 1)
        assert end == datetime.date(2025, 3, 31)

    def test_no_period(self) -> None:
        start, end = find_statement_period("No dates here")
        assert start is None
        assert end is None


class TestFindAccountHolder:
    def test_account_holder_label(self) -> None:
        assert find_account_holder("Account Holder: John Doe") == "John Doe"

    def test_name_label(self) -> None:
        assert find_account_holder("Name: Alice Smith") == "Alice Smith"

    def test_no_match(self) -> None:
        assert find_account_holder("No relevant info") is None
