"""Decision layer: policy + confidence → reviewable redaction suggestions.

Sits between fusion and redaction planning. The DecisionEngine never
redacts anything — it produces a ReviewPlan in which every detection
carries a *suggested* action (redact / keep / ask). The user (via the
CLI or the review UI) fills in decisions; ``ReviewPlan.resolve()`` then
yields the detections that are actually redacted.

The ReviewPlan is JSON-serialisable and is the contract between the
engine, the CLI, and the review UI.
"""

from __future__ import annotations

import enum
import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from privacy_firewall.models.detection import Detection
from privacy_firewall.policy.models import Policy, PolicyAction

SCHEMA_VERSION = 1


class SuggestedAction(enum.StrEnum):
    """The engine's suggestion for one detection."""

    REDACT = "redact"
    KEEP = "keep"
    ASK = "ask"


class ReviewDecision(enum.StrEnum):
    """The user's final decision for one detection."""

    REDACT = "redact"
    KEEP = "keep"


class ReviewEntry(BaseModel):
    """One detection with its suggested action and (eventual) user decision.

    Everything except ``decision`` is set by the DecisionEngine;
    ``decision`` starts as ``None`` and is filled during review.
    """

    detection: Detection
    suggested_action: SuggestedAction
    suggestion_reasons: tuple[str, ...] = ()
    decision: ReviewDecision | None = None

    @property
    def detection_id(self) -> str:
        """Stable identifier of the underlying detection."""
        return self.detection.detection_id

    @property
    def effective_action(self) -> SuggestedAction:
        """The decision if made, otherwise the suggestion."""
        if self.decision is not None:
            return SuggestedAction(self.decision.value)
        return self.suggested_action


class ReviewPlan(BaseModel):
    """A serialisable review session for one source document."""

    model_config = ConfigDict(validate_assignment=True)

    schema_version: int = SCHEMA_VERSION
    source_path: str
    source_sha256: str
    policy_name: str
    entries: list[ReviewEntry] = []

    def entry_by_id(self, detection_id: str) -> ReviewEntry | None:
        """Return the entry with the given detection id, or ``None``."""
        for entry in self.entries:
            if entry.detection_id == detection_id:
                return entry
        return None

    def pending_entries(self) -> list[ReviewEntry]:
        """Entries suggested as ASK that have no user decision yet."""
        return [
            e
            for e in self.entries
            if e.decision is None and e.suggested_action == SuggestedAction.ASK
        ]

    def counts(self) -> dict[str, int]:
        """Summary of effective actions (redact / keep / ask)."""
        summary = {"redact": 0, "keep": 0, "ask": 0}
        for entry in self.entries:
            summary[entry.effective_action.value] += 1
        return summary

    def resolve(self, *, accept_suggestions: bool = False) -> list[Detection]:
        """Return the detections to redact.

        Args:
            accept_suggestions: When ``True``, entries without a user
                decision fall back to their suggestion — and unresolved
                *ask* entries are redacted (privacy-first: never expose
                information the engine was unsure about without a human
                explicitly keeping it).

        Returns:
            Detections whose effective action is *redact*.

        Raises:
            ValueError: If entries are undecided and *accept_suggestions*
                is ``False``.
        """
        if not accept_suggestions:
            undecided = [e for e in self.entries if e.decision is None]
            if undecided:
                msg = (
                    f"{len(undecided)} entries have no decision; review them "
                    "or resolve with accept_suggestions=True"
                )
                raise ValueError(msg)

        to_redact: list[Detection] = []
        for entry in self.entries:
            if entry.decision is not None:
                if entry.decision == ReviewDecision.REDACT:
                    to_redact.append(entry.detection)
            elif entry.suggested_action in (SuggestedAction.REDACT, SuggestedAction.ASK):
                to_redact.append(entry.detection)
        return to_redact


def file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DecisionEngine:
    """Maps fused detections to suggested actions using a Policy."""

    def decide(
        self,
        detections: list[Detection],
        policy: Policy,
        *,
        source_path: str,
        source_sha256: str,
    ) -> ReviewPlan:
        """Build a ReviewPlan for the given detections.

        Args:
            detections: Fused, context-scored detections.
            policy: The policy providing per-type actions and bands.
            source_path: Path of the source document (recorded for audit).
            source_sha256: Hash of the source document (verified on apply).

        Returns:
            A ReviewPlan with one entry per detection, no decisions made.
        """
        entries = [
            self._entry_for(detection, policy)
            for detection in sorted(
                detections, key=lambda d: (d.page_number, d.span.start, d.detection_type)
            )
        ]
        return ReviewPlan(
            source_path=source_path,
            source_sha256=source_sha256,
            policy_name=policy.name,
            entries=entries,
        )

    @staticmethod
    def _entry_for(detection: Detection, policy: Policy) -> ReviewEntry:
        """Suggest an action for one detection."""
        type_policy = policy.type_policy(detection.detection_type)

        if detection.text in type_policy.allow_values:
            action = SuggestedAction.KEEP
            reasons = ("value is allow-listed by the policy",)
        elif type_policy.action == PolicyAction.KEEP:
            action = SuggestedAction.KEEP
            reasons = (f"policy '{policy.name}' keeps {detection.detection_type}",)
        elif type_policy.action == PolicyAction.ASK:
            action = SuggestedAction.ASK
            reasons = (f"policy '{policy.name}' defers {detection.detection_type} to review",)
        elif detection.confidence >= policy.auto_redact_above:
            action = SuggestedAction.REDACT
            reasons = (
                f"confidence {detection.confidence:.2f} >= "
                f"auto-redact threshold {policy.auto_redact_above:.2f}",
            )
        elif detection.confidence >= policy.ask_above:
            action = SuggestedAction.ASK
            reasons = (
                f"confidence {detection.confidence:.2f} in the ask band "
                f"[{policy.ask_above:.2f}, {policy.auto_redact_above:.2f})",
            )
        else:
            action = SuggestedAction.KEEP
            reasons = (
                f"confidence {detection.confidence:.2f} below the ask "
                f"threshold {policy.ask_above:.2f} (probable noise)",
            )

        return ReviewEntry(
            detection=detection,
            suggested_action=action,
            suggestion_reasons=reasons,
        )
