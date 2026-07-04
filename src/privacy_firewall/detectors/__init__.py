"""Detector package for identifying sensitive information in documents.

Exports all built-in detector classes along with the registry, base class,
and result types that downstream consumers use to run and collect scans.
"""

from privacy_firewall.detectors.aadhaar_detector import AadhaarDetector
from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.detectors.email_detector import EmailDetector
from privacy_firewall.detectors.pan_detector import PANDetector
from privacy_firewall.detectors.phone_detector import PhoneDetector
from privacy_firewall.detectors.regex_detector import RegexDetector
from privacy_firewall.detectors.registry import DetectorRegistry
from privacy_firewall.detectors.result import DetectionResult, DetectorRun, timed_scan
from privacy_firewall.detectors.upi_detector import UpiDetector

__all__ = [
    "AadhaarDetector",
    "BaseDetector",
    "DetectionResult",
    "DetectorRegistry",
    "DetectorRun",
    "EmailDetector",
    "PANDetector",
    "PhoneDetector",
    "RegexDetector",
    "timed_scan",
    "UpiDetector",
]
