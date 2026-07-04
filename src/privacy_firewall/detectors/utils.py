"""Shared utility helpers used across detectors."""

from __future__ import annotations

import re

from privacy_firewall.models.detection import Detection


def is_exact_duplicate(detections: list[Detection], text: str) -> bool:
    """Check if *text* already exists in the detection list (exact match).

    Args:
        detections: The current list of detections.
        text: The candidate text to check.

    Returns:
        ``True`` if *text* is already present among the detections.
    """
    return any(d.text == text for d in detections)


def is_containment_duplicate(detections: list[Detection], normalized: str) -> bool:
    """Check if a normalised string is a duplicate via containment.

    Handles overlapping or reformatted variants (e.g. ``+91-9876543210``
    vs ``9876543210``) where one contains the other.

    Args:
        detections: The current list of detections.
        normalized: The digits-only representation of the candidate.

    Returns:
        ``True`` if the candidate is considered a duplicate.
    """
    for d in detections:
        existing = re.sub(r"[^\d]", "", d.text)
        if normalized in existing or existing in normalized:
            return True
    return False
