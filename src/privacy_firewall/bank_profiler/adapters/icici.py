"""ICICI bank-statement profiler."""
from __future__ import annotations

from privacy_firewall.bank_profiler.adapters._base_profiler import _BaseBankProfiler
from privacy_firewall.bank_profiler.adapters._patterns import ICICI_ACCOUNT_RES
from privacy_firewall.bank_profiler.models import BankName


class ICICIProfiler(_BaseBankProfiler):
    name = "icici"
    bank_name = BankName.ICICI
    name_aliases = {"icici bank", "icici", "icici bank ltd", "icici ltd"}
    ifsc_prefixes = {"ICIC"}
    account_patterns = ICICI_ACCOUNT_RES
