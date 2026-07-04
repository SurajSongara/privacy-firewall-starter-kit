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
    tier = DETECTOR_TIERS.get(detector_name, "heuristic")
    return PRIORITY_TIERS.get(tier, 0)


def spans_overlap(a: Span, b: Span) -> bool:
    return a.start < b.end and b.start < a.end


@dataclass
class MergeRecord:
    kept: Detection
    merged: list[Detection]
    reason: str


@dataclass
class FusionResult:
    detections: list[Detection]
    merge_log: list[MergeRecord] = field(default_factory=list)


class FusionEngine:
    def fuse(self, detections: list[Detection]) -> FusionResult:
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
    winner_pri = detector_priority(winner.detector_name)
    loser_pri = detector_priority(loser.detector_name)
    if winner_pri > loser_pri:
        return f"higher priority tier ({winner.detector_name}>{loser.detector_name})"
    if loser_pri > winner_pri:
        return f"lower priority tier ({loser.detector_name}>{winner.detector_name})"
    return f"higher confidence ({winner.confidence:.2f}>{loser.confidence:.2f})"
