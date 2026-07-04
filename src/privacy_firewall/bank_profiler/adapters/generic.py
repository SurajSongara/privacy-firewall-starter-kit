"""Generic bank-statement profiler (fallback)."""
from __future__ import annotations

from privacy_firewall.bank_profiler._helpers import (
    extract_all_text,
    find_account_holder,
    find_ifsc,
    find_statement_period,
)
from privacy_firewall.bank_profiler.models import BankName, BankProfile
from privacy_firewall.bank_profiler.provider import BankProfiler
from privacy_firewall.models.document import Document


class GenericProfiler(BankProfiler):
    """Fallback profiler that identifies basic metadata without a specific bank."""

    name = "generic"

    def profile(self, document: Document) -> BankProfile:
        text = extract_all_text(document)

        ifsc_code = find_ifsc(text)
        start, end = find_statement_period(text)
        holder = find_account_holder(text)

        confidence = 0.1
        if ifsc_code:
            confidence += 0.1
        if start:
            confidence += 0.1
        if holder:
            confidence += 0.1

        return BankProfile(
            bank_name=BankName.GENERIC,
            confidence=min(confidence, 1.0),
            ifsc_code=ifsc_code,
            account_holder=holder,
            statement_start=start,
            statement_end=end,
            page_count=len(document.pages),
        )
