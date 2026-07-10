"""Resolve a policy by builtin name or from a YAML/JSON file."""

from __future__ import annotations

import json
from pathlib import Path

from privacy_firewall.policy.models import Policy
from privacy_firewall.policy.presets import BUILTIN_POLICIES


def list_policies() -> list[str]:
    """Return the names of all builtin policies."""
    return sorted(BUILTIN_POLICIES)


def get_policy(name_or_path: str) -> Policy:
    """Resolve a policy from a builtin name or a file path.

    Args:
        name_or_path: A builtin policy name (``share-with-ai``, ``kyc``,
            ``minimal``) or a path to a ``.yaml``/``.yml``/``.json`` file.

    Returns:
        The resolved, validated Policy.

    Raises:
        ValueError: If the name is unknown and no such file exists, or the
            file has an unsupported extension.
    """
    builtin = BUILTIN_POLICIES.get(name_or_path)
    if builtin is not None:
        return builtin

    path = Path(name_or_path)
    if not path.exists():
        msg = (
            f"Unknown policy {name_or_path!r}. "
            f"Builtin policies: {', '.join(list_policies())}; "
            "or pass a path to a .yaml/.json policy file."
        )
        raise ValueError(msg)

    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        import yaml

        data = yaml.safe_load(path.read_text())
    elif suffix == ".json":
        data = json.loads(path.read_text())
    else:
        msg = f"Unsupported policy file type {suffix!r} (use .yaml, .yml, or .json)"
        raise ValueError(msg)

    return Policy.model_validate(data)
