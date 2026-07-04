"""Shared helpers used by concrete bank profilers."""
from __future__ import annotations

import datetime
import re

from privacy_firewall.bank_profiler.models import (
    ACCOUNT_HOLDER_RES,
    IFSC_RE,
    STATEMENT_PERIOD_RES,
)
from privacy_firewall.models.document import Document

_PAGE_DATE_RE = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})\b")


def extract_all_text(document: Document) -> str:
    """Return all text in the document, separated by newlines.

    Args:
        document: The parsed document.

    Returns:
        A single string of all text blocks.
    """
    lines: list[str] = []
    for page in document.pages:
        for block in page.blocks:
            if hasattr(block, "text") and block.text:
                lines.append(str(block.text))
    return "\n".join(lines)


def find_ifsc(text: str) -> str | None:
    """Return the first IFSC code found in *text*, or ``None``.

    Args:
        text: The text to search.

    Returns:
        The matched IFSC code or ``None``.
    """
    m = IFSC_RE.search(text)
    return m.group(0) if m else None


def find_account_number(text: str, patterns: list[re.Pattern[str]]) -> str | None:
    """Return the first account number matching any of *patterns*, or ``None``.

    Args:
        text: The text to search.
        patterns: A list of compiled regex patterns.

    Returns:
        The matched account number or ``None``.
    """
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m.group(0)
    return None


def find_statement_period(
    text: str,
) -> tuple[datetime.date | None, datetime.date | None]:
    """Find statement start and end dates in *text*.

    Args:
        text: The text to search.

    Returns:
        A ``(start, end)`` tuple, both may be ``None``.
    """
    for pat in STATEMENT_PERIOD_RES:
        m = pat.search(text)
        if m:
            start = _parse_date(m.group(1))
            end = _parse_date(m.group(2))
            return start, end
    return None, None


def find_account_holder(text: str) -> str | None:
    """Find the account holder name in *text*.

    Args:
        text: The text to search.

    Returns:
        The first matched name or ``None``.
    """
    for pat in ACCOUNT_HOLDER_RES:
        m = pat.search(text)
        if m:
            return m.group(1).strip()
    return None


def _parse_date(value: str) -> datetime.date | None:
    """Try to parse *value* as a date in known formats.

    Args:
        value: Date string.

    Returns:
        A ``date`` or ``None``.
    """
    for fmt in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None
