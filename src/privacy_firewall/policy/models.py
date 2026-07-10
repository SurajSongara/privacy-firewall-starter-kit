"""Policy models: what to do with detections, per type and confidence band.

A policy never affects *detection* — detectors report facts. The policy
maps each detection to a suggested action (redact / keep / ask) that the
user can override during review.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, model_validator


class PolicyAction(enum.StrEnum):
    """Default handling for a detection type."""

    REDACT = "redact"
    """Redact (subject to the confidence bands)."""

    KEEP = "keep"
    """Never redact this type."""

    ASK = "ask"
    """Always defer to the user."""


class TypePolicy(BaseModel):
    """Policy overrides for one detection type."""

    model_config = ConfigDict(frozen=True)

    action: PolicyAction = PolicyAction.REDACT
    allow_values: tuple[str, ...] = ()
    """Exact values that are always kept (e.g. a public helpline number)."""


class Policy(BaseModel):
    """A named redaction policy.

    Confidence bands apply when the effective action is ``REDACT``:
    at or above ``auto_redact_above`` the suggestion is *redact*; at or
    above ``ask_above`` it is *ask*; below that the detection is left
    alone (*keep*) as probable noise.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    default_action: PolicyAction = PolicyAction.REDACT
    auto_redact_above: float = 0.9
    ask_above: float = 0.5
    types: dict[str, TypePolicy] = {}

    @model_validator(mode="after")
    def _bands_ordered(self) -> Policy:
        """Validate that 0 <= ask_above <= auto_redact_above <= 1."""
        if not 0.0 <= self.ask_above <= self.auto_redact_above <= 1.0:
            msg = (
                "confidence bands must satisfy "
                "0 <= ask_above <= auto_redact_above <= 1 "
                f"(got ask_above={self.ask_above}, auto_redact_above={self.auto_redact_above})"
            )
            raise ValueError(msg)
        return self

    def type_policy(self, detection_type: str) -> TypePolicy:
        """Return the policy for a detection type, falling back to the default.

        Args:
            detection_type: e.g. ``"PAN"``, ``"AADHAAR"``.

        Returns:
            The configured TypePolicy, or one built from ``default_action``.
        """
        configured = self.types.get(detection_type)
        if configured is not None:
            return configured
        return TypePolicy(action=self.default_action)
