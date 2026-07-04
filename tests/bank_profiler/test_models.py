"""Tests for bank-profiler models."""
from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from privacy_firewall.bank_profiler.models import BankName, BankProfile


class TestBankName:
    def test_str_values(self) -> None:
        assert str(BankName.SBI) == "sbi"
        assert str(BankName.HDFC) == "hdfc"
        assert str(BankName.ICICI) == "icici"
        assert str(BankName.AXIS) == "axis"
        assert str(BankName.GENERIC) == "generic"


class TestBankProfile:
    def test_minimal(self) -> None:
        p = BankProfile(bank_name=BankName.SBI, confidence=0.8)
        assert p.bank_name == BankName.SBI
        assert p.confidence == 0.8

    def test_frozen(self) -> None:
        p = BankProfile(bank_name=BankName.SBI, confidence=0.8)
        with pytest.raises((TypeError, ValueError)):
            p.bank_name = BankName.HDFC  # type: ignore[misc]

    def test_full(self) -> None:
        p = BankProfile(
            bank_name=BankName.HDFC,
            confidence=0.95,
            account_number="12345678901234",
            ifsc_code="HDFC0001234",
            account_holder="John Doe",
            statement_start=datetime.date(2024, 4, 1),
            statement_end=datetime.date(2025, 3, 31),
            page_count=5,
        )
        assert p.account_number == "12345678901234"
        assert p.ifsc_code == "HDFC0001234"
        assert p.account_holder == "John Doe"
        assert p.page_count == 5

    def test_confidence_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            BankProfile(bank_name=BankName.SBI, confidence=1.5)

    def test_confidence_negative(self) -> None:
        with pytest.raises(ValidationError):
            BankProfile(bank_name=BankName.SBI, confidence=-0.1)
