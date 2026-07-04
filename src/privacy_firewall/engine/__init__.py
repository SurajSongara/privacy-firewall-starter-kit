"""Detection-fusion engine for merging overlapping detections."""

from privacy_firewall.engine.fusion import (
    DETECTOR_TIERS,
    PRIORITY_TIERS,
    FusionEngine,
    FusionResult,
    MergeRecord,
    detector_priority,
    spans_overlap,
)
from privacy_firewall.engine.redaction import (
    Redaction,
    RedactionPlan,
    RedactionPlanner,
    RedactionType,
)

__all__ = [
    "DETECTOR_TIERS",
    "FusionEngine",
    "FusionResult",
    "MergeRecord",
    "PRIORITY_TIERS",
    "Redaction",
    "RedactionPlan",
    "RedactionPlanner",
    "RedactionType",
    "detector_priority",
    "spans_overlap",
]
