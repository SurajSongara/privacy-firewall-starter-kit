"""Data models for bank-statement profiling."""
from __future__ import annotations

import datetime
import enum
import re

from pydantic import BaseModel, ConfigDict, Field


class BankName(enum.StrEnum):
    """Supported bank identifiers."""

    SBI = "sbi"
    HDFC = "hdfc"
    ICICI = "icici"
    AXIS = "axis"
    GENERIC = "generic"


class BankProfile(BaseModel):
    """Metadata profile of a bank statement document.

    Attributes:
        bank_name: The identified bank.
        confidence: Confidence score in [0, 1].
        account_number: Account number found, if any.
        ifsc_code: IFSC code found, if any.
        account_holder: Account holder name, if any.
        statement_start: Statement period start date.
        statement_end: Statement period end date.
        page_count: Number of pages in the document.
        metadata: Additional key-value observations.
    """

    model_config = ConfigDict(frozen=True)

    bank_name: BankName
    confidence: float = Field(ge=0.0, le=1.0)
    account_number: str | None = None
    ifsc_code: str | None = None
    account_holder: str | None = None
    statement_start: datetime.date | None = None
    statement_end: datetime.date | None = None
    page_count: int = 0
    metadata: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shared patterns used by all profilers
# ---------------------------------------------------------------------------

IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
"""IFSC code pattern: 4 letters + 0 + 6 alphanumeric."""

_MONTH = r"[A-Z][a-z]+"

STATEMENT_PERIOD_RES = [
    re.compile(
        rf"(?:statement\s+)?period\s*[:\-]?\s*"
        rf"(\d{{1,2}}\s+{_MONTH}\s+\d{{4}})\s*(?:to|-|–)\s*"
        rf"(\d{{1,2}}\s+{_MONTH}\s+\d{{4}})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:statement\s+)?period\s*[:\-]?\s*"
        r"(\d{1,2}/\d{1,2}/\d{4})\s*(?:to|-|–)\s*"
        r"(\d{1,2}/\d{1,2}/\d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        rf"from\s+(\d{{1,2}}\s+{_MONTH}\s+\d{{4}})\s*(?:to|-|–)\s*"
        rf"(\d{{1,2}}\s+{_MONTH}\s+\d{{4}})",
        re.IGNORECASE,
    ),
]
"""Common patterns for statement period ranges."""

ACCOUNT_HOLDER_RES = [
    re.compile(r"(?:account\s+)?(?:holder|name)\s*[:\-]?\s*([A-Z][A-Za-z.\s]+)", re.IGNORECASE),
    re.compile(
        r"(?:customer|accounter)\s+(?:name|id)\s*[:\-]?\s*([A-Z][A-Za-z.\s]+)",
        re.IGNORECASE,
    ),
]
"""Common patterns for account-holder name."""
