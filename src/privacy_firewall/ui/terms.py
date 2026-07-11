"""Workspace terms: manual marks remembered across documents.

A studio workspace can carry a small, user-curated list of terms that
should be *suggested* for redaction in every document reviewed there —
the reviewer marks a name once and later documents open with its
instances pre-suggested (never pre-decided). The list lives in
``<workspace>/.privacy-firewall/terms.json``, is opt-in, local-only,
and deletable; the engine owns all reads and writes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

SCHEMA_VERSION = 1

STORE_DIRNAME = ".privacy-firewall"
STORE_FILENAME = "terms.json"


@dataclass(frozen=True)
class WorkspaceTerm:
    """One remembered term.

    Attributes:
        text: The text to suggest for marking (whitespace-flexible match).
        label: Detection-type label (e.g. ``NAME``).
        case_sensitive: Require an exact-case match.
        added_from: Filename of the document the term was first marked in.
    """

    text: str
    label: str
    case_sensitive: bool = False
    added_from: str = ""

    @property
    def key(self) -> tuple[str, str]:
        """Identity of a term: its text (case-folded) and label."""
        return (self.text.casefold(), self.label)


class TermsStore:
    """Persistent store for one workspace's remembered terms."""

    def __init__(self, path: Path) -> None:
        """Load the store from *path* (missing or corrupt files mean empty).

        Args:
            path: The ``terms.json`` file location.
        """
        self.path = Path(path)
        self.terms: list[WorkspaceTerm] = []
        self._ignored: set[tuple[str, str]] = set()
        self._load()

    @classmethod
    def for_workspace(cls, workspace: Path) -> TermsStore:
        """The store for a studio workspace folder."""
        return cls(Path(workspace) / STORE_DIRNAME / STORE_FILENAME)

    def add(
        self,
        text: str,
        label: str,
        *,
        case_sensitive: bool = False,
        added_from: str = "",
    ) -> bool:
        """Remember a term (idempotent). Returns ``True`` if newly added.

        Adding a term also clears any keep-allowlist entry for it — the
        user's newest instruction wins.
        """
        term = WorkspaceTerm(
            text=text.strip(),
            label=label.strip().upper(),
            case_sensitive=case_sensitive,
            added_from=added_from,
        )
        if not term.text or not term.label:
            msg = "term text and label must not be blank"
            raise ValueError(msg)
        self._ignored.discard(term.key)
        if any(existing.key == term.key for existing in self.terms):
            self._save()
            return False
        self.terms.append(term)
        self._save()
        return True

    def remove(self, text: str, label: str) -> bool:
        """Forget a term workspace-wide. Returns ``True`` if it existed."""
        key = (text.casefold(), label.strip().upper())
        before = len(self.terms)
        self.terms = [t for t in self.terms if t.key != key]
        if len(self.terms) == before:
            return False
        self._save()
        return True

    def ignore(self, text: str, label: str) -> None:
        """Allowlist a term: keep it stored but stop suggesting it."""
        self._ignored.add((text.casefold(), label.strip().upper()))
        self._save()

    def is_ignored(self, term: WorkspaceTerm) -> bool:
        """Whether the term is on the keep-allowlist."""
        return term.key in self._ignored

    def active_terms(self) -> list[WorkspaceTerm]:
        """Terms that should be suggested (stored minus allowlisted)."""
        return [t for t in self.terms if not self.is_ignored(t)]

    def _load(self) -> None:
        """Read the JSON file; missing or unreadable files leave the store empty."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for item in data.get("terms", []):
            try:
                self.terms.append(
                    WorkspaceTerm(
                        text=str(item["text"]),
                        label=str(item["label"]),
                        case_sensitive=bool(item.get("case_sensitive", False)),
                        added_from=str(item.get("added_from", "")),
                    )
                )
            except (KeyError, TypeError):
                continue
        for item in data.get("ignored", []):
            try:
                self._ignored.add((str(item["text"]).casefold(), str(item["label"])))
            except (KeyError, TypeError):
                continue

    def _save(self) -> None:
        """Persist the store, creating the workspace dot-folder if needed."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "terms": [asdict(t) for t in self.terms],
            "ignored": [{"text": text, "label": label} for text, label in sorted(self._ignored)],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
