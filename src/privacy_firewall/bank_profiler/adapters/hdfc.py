"""HDFC bank-statement profiler."""
from __future__ import annotations

from privacy_firewall.bank_profiler.adapters._base_profiler import _BaseBankProfiler
from privacy_firewall.bank_profiler.adapters._patterns import HDFC_ACCOUNT_RES
from privacy_firewall.bank_profiler.models import BankName


class HDFCProfiler(_BaseBankProfiler):
    name = "hdfc"
    bank_name = BankName.HDFC
    name_aliases = {"hdfc bank", "hdfc", "hdfc bank ltd", "hdfc ltd"}
    ifsc_prefixes = {"HDFC"}
    account_patterns = HDFC_ACCOUNT_RES
