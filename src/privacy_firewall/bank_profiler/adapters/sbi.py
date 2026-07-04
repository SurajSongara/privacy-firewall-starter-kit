"""SBI bank-statement profiler."""
from __future__ import annotations

from privacy_firewall.bank_profiler.adapters._base_profiler import _BaseBankProfiler
from privacy_firewall.bank_profiler.adapters._patterns import SBI_ACCOUNT_RES
from privacy_firewall.bank_profiler.models import BankName


class SBIProfiler(_BaseBankProfiler):
    name = "sbi"
    bank_name = BankName.SBI
    name_aliases = {"state bank of india", "sbi", "sbi bank", "state bank"}
    ifsc_prefixes = {"SBIN"}
    account_patterns = SBI_ACCOUNT_RES
