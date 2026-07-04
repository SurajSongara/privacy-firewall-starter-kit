"""Base class for bank-specific profilers."""
from __future__ import annotations

import re

from privacy_firewall.bank_profiler._helpers import (
    extract_all_text,
    find_account_holder,
    find_account_number,
    find_ifsc,
    find_statement_period,
)
from privacy_firewall.bank_profiler.models import BankName, BankProfile
from privacy_firewall.bank_profiler.provider import BankProfiler
from privacy_firewall.models.document import Document


class _BaseBankProfiler(BankProfiler):
    """Base that implements the shared :meth:`profile` logic.

    Subclasses set class-level attributes for bank identity and patterns.
    """

    name = "_base"
    bank_name: BankName = BankName.GENERIC
    """Which bank this profiler targets."""

    name_aliases: set[str] = set()
    """Case-folded name aliases (e.g. ``{\"state bank of india\", \"sbi\"}``)."""

    ifsc_prefixes: set[str] = set()
    """IFSC prefixes (e.g. ``{\"SBIN\"}``)."""

    account_patterns: list[re.Pattern[str]] = []
    """Regex patterns for account numbers specific to this bank."""

    def profile(self, document: Document) -> BankProfile:
        text = extract_all_text(document)
        text_lower = text.lower()

        score = 0.0
        ifsc_code = find_ifsc(text)
        acct_no: str | None = None
        holder: str | None = None
        start_date, end_date = None, None

        # IFSC match
        if ifsc_code:
            prefix = ifsc_code[:4]
            if prefix in self.ifsc_prefixes:
                score += 0.5
            else:
                return BankProfile(
                    bank_name=self.bank_name,
                    confidence=0.0,
                    page_count=len(document.pages),
                )

        # Name alias match
        for alias in self.name_aliases:
            if alias in text_lower:
                score += 0.3
                break

        # Account number
        if self.account_patterns:
            acct_no = find_account_number(text, self.account_patterns)

        # Statement period
        start_date, end_date = find_statement_period(text)

        # Account holder
        holder = find_account_holder(text)

        return BankProfile(
            bank_name=self.bank_name,
            confidence=min(score, 1.0),
            account_number=acct_no,
            ifsc_code=ifsc_code,
            account_holder=holder,
            statement_start=start_date,
            statement_end=end_date,
            page_count=len(document.pages),
        )
