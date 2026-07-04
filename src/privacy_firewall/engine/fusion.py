"""Detection-fusion logic: priority-based merging of overlapping detections."""

from __future__ import annotations

from dataclasses import dataclass, field

from privacy_firewall.models.detection import Detection
from privacy_firewall.models.geometry import Span

PRIORITY_TIERS: dict[str, int] = {
    "regex": 5,
    "validator": 4,
    "heuristic": 3,
    "ner": 2,
    "llm": 1,
}

DETECTOR_TIERS: dict[str, str] = {
    "pan": "regex",
    "aadhaar": "regex",
    "email": "regex",
    "phone": "regex",
    "upi": "regex",
}


def detector_priority(detector_name: str) -> int:
    """Return the numeric priority for a given detector name.

    Higher numbers indicate higher priority.

    Args:
        detector_name: Name of the detector (e.g. ``"pan"``, ``"email"``).

    Returns:
        Numeric priority value.
    """
    tier = DETECTOR_TIERS.get(detector_name, "heuristic")
    return PRIORITY_TIERS.get(tier, 0)


def spans_overlap(a: Span, b: Span) -> bool:
    """Check whether two character spans overlap in the same document.

    Args:
        a: First span.
        b: Second span.

    Returns:
        True if the spans overlap.
    """
    return a.start < b.end and b.start < a.end


@dataclass
class MergeRecord:
    """Records the outcome of merging one detection into another.

    Attributes:
        kept: The detection that was kept after merging.
        merged: The detections that were merged into the kept one.
        reason: Human-readable explanation for why this merge happened.
    """

    kept: Detection
    merged: list[Detection]
    reason: str


@dataclass
class FusionResult:
    """Result produced by the fusion engine after merging overlapping detections.

    Attributes:
        detections: The fused (deduplicated) list of detections.
        merge_log: Log of every merge operation that was performed.
    """

    detections: list[Detection]
    merge_log: list[MergeRecord] = field(default_factory=list)


class FusionEngine:
    """Merges overlapping detections by priority tier and confidence."""

    def fuse(self, detections: list[Detection]) -> FusionResult:
        """Merge overlapping detections grouped by page and detection type.

        Args:
            detections: Raw list of detections to fuse.

        Returns:
            A FusionResult containing the deduplicated detections and merge log.
        """
        log: list[MergeRecord] = []

        groups: dict[tuple[int, str], list[Detection]] = {}
        for d in detections:
            key = (d.page_number, d.detection_type)
            groups.setdefault(key, []).append(d)

        fused: list[Detection] = []
        for key in sorted(groups):
            group = groups[key]
            merged = self._merge_group(group, log)
            fused.extend(merged)

        return FusionResult(detections=fused, merge_log=log)

    @staticmethod
    def _merge_group(
        group: list[Detection], log: list[MergeRecord]
    ) -> list[Detection]:
        """Merge a single group of same-type detections from the same page.

        Detections are sorted by span start, then priority, then confidence.
        Overlapping neighbours are resolved and logged.

        Args:
            group: Detections sharing the same page and detection type.
            log: Accumulator for merge records.

        Returns:
            The merged list of detections.
        """
        sorted_detections = sorted(
            group,
            key=lambda d: (d.span.start, -detector_priority(d.detector_name), -d.confidence),
        )

        result: list[Detection] = []
        for d in sorted_detections:
            if result and spans_overlap(result[-1].span, d.span):
                winner, loser = _resolve(result[-1], d)
                log.append(
                    MergeRecord(
                        kept=winner,
                        merged=[loser],
                        reason=_merge_reason(winner, loser),
                    )
                )
                result[-1] = winner
            else:
                result.append(d)

        return result


def _resolve(a: Detection, b: Detection) -> tuple[Detection, Detection]:
    """Resolve two overlapping detections by choosing the higher-priority one.

    Priority is determined first by detector tier, then by confidence.

    Args:
        a: First detection.
        b: Second detection.

    Returns:
        A tuple ``(winner, loser)``.
    """
    a_pri = detector_priority(a.detector_name)
    b_pri = detector_priority(b.detector_name)
    if a_pri > b_pri:
        return a, b
    if b_pri > a_pri:
        return b, a
    if a.confidence >= b.confidence:
        return a, b
    return b, a


def _merge_reason(winner: Detection, loser: Detection) -> str:
    """Generate a human-readable reason explaining why winner beat loser.

    Args:
        winner: The detection that was kept.
        loser: The detection that was merged away.

    Returns:
        A short string describing the merge rationale.
    """
    winner_pri = detector_priority(winner.detector_name)
    loser_pri = detector_priority(loser.detector_name)
    if winner_pri > loser_pri:
        return f"higher priority tier ({winner.detector_name}>{loser.detector_name})"
    if loser_pri > winner_pri:
        return f"lower priority tier ({loser.detector_name}>{winner.detector_name})"
    return f"higher confidence ({winner.confidence:.2f}>{loser.confidence:.2f})"
