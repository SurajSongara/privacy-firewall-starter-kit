"""Policy layer: decides what to do with detections (redact / keep / ask)."""

from privacy_firewall.policy.loader import get_policy, list_policies
from privacy_firewall.policy.models import Policy, PolicyAction, TypePolicy
from privacy_firewall.policy.presets import BUILTIN_POLICIES, DEFAULT_POLICY_NAME

__all__ = [
    "BUILTIN_POLICIES",
    "DEFAULT_POLICY_NAME",
    "Policy",
    "PolicyAction",
    "TypePolicy",
    "get_policy",
    "list_policies",
]
