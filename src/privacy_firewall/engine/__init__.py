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
from privacy_firewall.engine.hybrid_merger import BlockProvenance, HybridMerger, MergeResult
from privacy_firewall.engine.redaction import (
    Redaction,
    RedactionPlan,
    RedactionPlanner,
    RedactionType,
)

__all__ = [
    "BlockProvenance",
    "DETECTOR_TIERS",
    "FusionEngine",
    "FusionResult",
    "HybridMerger",
    "MergeRecord",
    "MergeResult",
    "PRIORITY_TIERS",
    "Redaction",
    "RedactionPlan",
    "RedactionPlanner",
    "RedactionType",
    "detector_priority",
    "spans_overlap",
]
