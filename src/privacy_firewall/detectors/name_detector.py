"""Deterministic NAME detection from evidence already in the document.

No language model and no dictionary of names: candidate name tokens are
*derived* from structured PII the document itself carries — email local
parts, profile handles (LinkedIn/GitHub), and the page-1 title line —
then every occurrence of a candidate is reported, including inside
longer tokens such as ``SurajSongara_DE_v1.pdf``.

Confidence follows corroboration: a token supported by two independent
evidence kinds is high-confidence; a single-source token lands in the
ask band for the reviewer to confirm. The title line alone never
produces a candidate (bank statements open with "State Bank of India" —
a title is corroborating evidence, not originating evidence).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import Span

EMAIL_LOCAL_PATTERN = re.compile(r"([a-zA-Z0-9._%+-]+)@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
"""Email with its local part captured (evidence source, not detection)."""

HANDLE_PATTERN = re.compile(r"(?:linkedin\.com/in/|github\.com/)([A-Za-z0-9_-]{3,})", re.IGNORECASE)
"""Profile URLs whose path segment is usually the owner's name."""

CAMEL_TOKEN_PATTERN = re.compile(r"[A-Z][a-z]{2,}")
"""Capitalised runs inside camel-case handles like ``SurajSongara``."""

MIN_TOKEN_LENGTH = 4
"""Shorter fragments (``ram``, ``dev``) collide with ordinary words."""

HIGH_CONFIDENCE = 0.9
"""Token corroborated by at least two independent evidence kinds."""

SINGLE_SOURCE_CONFIDENCE = 0.6
"""Ask-band confidence for a token seen in only one evidence kind."""

TOKEN_STOPWORDS: frozenset[str] = frozenset(
    {
        # role/service words common in email local parts
        "work",
        "mail",
        "email",
        "info",
        "contact",
        "admin",
        "office",
        "hello",
        "team",
        "help",
        "support",
        "noreply",
        "reply",
        "test",
        "user",
        "official",
        "career",
        "careers",
        "jobs",
        "sales",
        # document words that surface in title lines
        "bank",
        "statement",
        "account",
        "india",
        "limited",
        "private",
        "resume",
        "curriculum",
        "vitae",
        "profile",
        "summary",
    }
)
"""Never name-candidates, whatever the evidence says."""

TITLE_MAX_CHARS = 40
TITLE_BLOCKS_CONSIDERED = 3
"""How far down page 1 a title line may sit."""


@dataclass
class _Candidate:
    """One candidate name token and the evidence kinds supporting it."""

    display: str
    sources: set[str] = field(default_factory=set)
    details: list[str] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        independent = self.sources - {"title"}
        if len(self.sources) >= 2 and independent:
            return HIGH_CONFIDENCE
        if independent:
            return SINGLE_SOURCE_CONFIDENCE
        return 0.0  # title-only evidence never detects on its own


class NameDetector(BaseDetector):
    """Detects person names derived from the document's own PII evidence."""

    @property
    def name(self) -> str:
        """Human-readable detector name."""
        return "name"

    def scan(self, document: Document, *, values_only: bool = False) -> list[Detection]:
        """Scan a document for occurrences of derived name candidates.

        Args:
            document: The document to scan.
            values_only: If ``True``, use per-span bounding boxes for
                precise value-only redaction.

        Returns:
            One Detection per occurrence of each accepted candidate.
        """
        candidates = self._collect_candidates(document)
        active = {token: cand for token, cand in candidates.items() if cand.confidence > 0.0}
        if not active:
            return []

        detections: list[Detection] = []
        for page in document.pages:
            for block in page.blocks:
                if not isinstance(block, TextBlock):
                    continue
                spans: list[tuple[int, int, str]] = []
                for token, cand in active.items():
                    pattern = re.compile(re.escape(token), re.IGNORECASE)
                    for match in pattern.finditer(block.text):
                        if not self._boundary_ok(block.text, match.start(), match.end()):
                            continue
                        spans.append((match.start(), match.end(), token))
                # Longest-first so a full handle swallows its own tokens.
                spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
                accepted: list[tuple[int, int]] = []
                for start, end, token in spans:
                    if any(a0 <= start and end <= a1 for a0, a1 in accepted):
                        continue  # covered by a longer accepted match
                    accepted.append((start, end))
                    cand = active[token]
                    detections.append(
                        Detection(
                            detector_name=self.name,
                            detection_type="NAME",
                            text=block.text[start:end],
                            span=Span(start=start, end=end),
                            bbox=(block.bbox_for_span(start, end) if values_only else block.bbox),
                            page_number=page.page_number,
                            confidence=cand.confidence,
                            reasons=tuple(cand.details),
                        )
                    )
        return detections

    def _collect_candidates(self, document: Document) -> dict[str, _Candidate]:
        """Derive candidate tokens from emails, handles, and the title line."""
        candidates: dict[str, _Candidate] = {}

        def support(token: str, source: str, detail: str) -> None:
            key = token.casefold()
            if len(key) < MIN_TOKEN_LENGTH or key in TOKEN_STOPWORDS or not key.isalpha():
                return
            cand = candidates.setdefault(key, _Candidate(display=token))
            if source not in cand.sources:
                cand.sources.add(source)
                cand.details.append(detail)

        full_text = "\n".join(
            block.text
            for page in document.pages
            for block in page.blocks
            if isinstance(block, TextBlock)
        )

        for match in EMAIL_LOCAL_PATTERN.finditer(full_text):
            local = match.group(1).split("+")[0]
            for token in re.split(r"[._\-%0-9]+", local):
                support(token, "email", f"derived from email local part '{local}'")

        slugs: list[str] = []
        for match in HANDLE_PATTERN.finditer(full_text):
            slug = match.group(1)
            slugs.append(slug)
            for token in CAMEL_TOKEN_PATTERN.findall(slug):
                support(token, "handle", f"derived from profile handle '{slug}'")

        # A lowercase slug can't be split, but containment corroborates
        # both ways: "suraj" ⊂ "surajsongara" lends the token handle
        # evidence and lends the slug the token's email evidence.
        for slug in slugs:
            folded = slug.casefold()
            slug_extra_sources: set[tuple[str, str]] = set()
            for key, cand in candidates.items():
                if key == folded or key not in folded:
                    continue
                if "handle" not in cand.sources:
                    cand.sources.add("handle")
                    cand.details.append(f"contained in profile handle '{slug}'")
                for source in cand.sources - {"handle", "title"}:
                    slug_extra_sources.add((source, key))
            if folded.isalpha():
                support(slug, "handle", f"profile handle '{slug}'")
                for source, key in slug_extra_sources:
                    support(slug, source, f"contains {source}-derived token '{key}'")

        for token, detail in self._title_tokens(document):
            support(token, "title", detail)

        return candidates

    @staticmethod
    def _title_tokens(document: Document) -> list[tuple[str, str]]:
        """Tokens of a page-1 title line (2-4 capitalised words).

        Title evidence only corroborates candidates from other sources —
        see :class:`_Candidate.confidence`.
        """
        if not document.pages:
            return []
        blocks = [b for b in document.pages[0].blocks if isinstance(b, TextBlock)]
        for block in blocks[:TITLE_BLOCKS_CONSIDERED]:
            text = block.text.strip()
            if not text or len(text) > TITLE_MAX_CHARS:
                continue
            words = text.split()
            if not 2 <= len(words) <= 4:
                continue
            if not all(w.isalpha() and w[0].isupper() for w in words):
                continue
            return [(w, f"appears in the title line '{text}'") for w in words]
        return []

    @staticmethod
    def _boundary_ok(text: str, start: int, end: int) -> bool:
        """Accept a match unless it melts into surrounding lowercase text.

        Matches flanked by non-letters always pass. Inside a longer
        word, only camel-case boundaries pass — ``Suraj`` and ``Songara``
        inside ``SurajSongara_DE`` are names, ``ram`` inside
        ``programme`` is not.
        """
        prev = text[start - 1] if start > 0 else ""
        nxt = text[end] if end < len(text) else ""
        left_ok = not prev.isalpha() or (prev.islower() and text[start].isupper())
        right_ok = not nxt.isalpha() or (text[end - 1].islower() and nxt.isupper())
        return left_ok and right_ok
