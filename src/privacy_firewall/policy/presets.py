"""Builtin policy presets for common sharing contexts."""

from __future__ import annotations

from privacy_firewall.policy.models import Policy, PolicyAction, TypePolicy

SHARE_WITH_AI = Policy(
    name="share-with-ai",
    description=(
        "Sanitise a document before uploading it to an AI assistant: "
        "redact every detected PII type."
    ),
    default_action=PolicyAction.REDACT,
)

KYC = Policy(
    name="kyc",
    description=(
        "Prepare a document for a KYC submission: identity numbers the "
        "receiver needs (PAN, Aadhaar) are kept, financial and contact "
        "details are redacted."
    ),
    default_action=PolicyAction.REDACT,
    types={
        "PAN": TypePolicy(action=PolicyAction.KEEP),
        "AADHAAR": TypePolicy(action=PolicyAction.KEEP),
    },
)

MINIMAL = Policy(
    name="minimal",
    description="Suggest nothing automatically: ask the user about every detection.",
    default_action=PolicyAction.ASK,
)

BUILTIN_POLICIES: dict[str, Policy] = {
    policy.name: policy for policy in (SHARE_WITH_AI, KYC, MINIMAL)
}

DEFAULT_POLICY_NAME = SHARE_WITH_AI.name
