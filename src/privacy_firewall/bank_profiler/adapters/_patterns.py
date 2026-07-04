"""Shared regex patterns used by bank-specific profilers."""
from __future__ import annotations

import re

SBI_ACCOUNT_RES = [
    re.compile(r"\b\d{11}\b"),
    re.compile(r"\b\d{15}\b"),
]

HDFC_ACCOUNT_RES = [
    re.compile(r"\b\d{14}\b"),
]

ICICI_ACCOUNT_RES = [
    re.compile(r"\b\d{12}\b"),
    re.compile(r"\b\d{15}\b"),
]

AXIS_ACCOUNT_RES = [
    re.compile(r"\b\d{15}\b"),
]
