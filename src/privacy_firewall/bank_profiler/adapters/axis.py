"""Axis bank-statement profiler."""
from __future__ import annotations

from privacy_firewall.bank_profiler.adapters._base_profiler import _BaseBankProfiler
from privacy_firewall.bank_profiler.adapters._patterns import AXIS_ACCOUNT_RES
from privacy_firewall.bank_profiler.models import BankName


class AxisProfiler(_BaseBankProfiler):
    name = "axis"
    bank_name = BankName.AXIS
    name_aliases = {"axis bank", "axis", "axis bank ltd"}
    ifsc_prefixes = {"UTIB", "AXIS"}
    account_patterns = AXIS_ACCOUNT_RES
