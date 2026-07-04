"""CLI command implementations for the privacy-firewall application."""

from privacy_firewall.cli.detect_cmd import detect_cmd
from privacy_firewall.cli.diagnostics_cmd import diagnostics_cmd
from privacy_firewall.cli.doctor_cmd import doctor_cmd
from privacy_firewall.cli.redact_cmd import redact_cmd
from privacy_firewall.cli.scan_cmd import scan_cmd

__all__ = [
    "detect_cmd",
    "diagnostics_cmd",
    "doctor_cmd",
    "redact_cmd",
    "scan_cmd",
]
