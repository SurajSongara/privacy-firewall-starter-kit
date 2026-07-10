"""Redaction planning: converts detections into a structured redaction plan."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import BoundingBox, Span


class RedactionType(enum.Enum):
    """Kind of redaction to apply to a detected region."""

    REPLACE = "replace"
    """Replace the detected text with a placeholder string."""

    BLACK_BAR = "black_bar"
    """Overlay a solid black bar over the detected region."""

    HIGHLIGHT = "highlight"
    """Highlight the region for manual review (no automatic redaction)."""


@dataclass
class Redaction:
    """A single redaction instruction targeting one detection.

    Attributes:
        detection: The detection that triggered this redaction.
        redaction_type: What kind of redaction to perform.
        replacement_text: Text to use when *redaction_type* is ``REPLACE``.
        page_number: Page where the redaction should be applied.
        span: Character span within the source block's text.
        bbox: Bounding box of the region to redact.
    """

    detection: Detection
    redaction_type: RedactionType
    replacement_text: str | None = None
    page_number: int = 0
    span: Span = field(default_factory=lambda: Span(start=0, end=1))
    bbox: BoundingBox = field(default_factory=lambda: BoundingBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0))


@dataclass
class RedactionPlan:
    """Structured plan describing all redactions to perform on a document.

    Attributes:
        redactions: Ordered list of redaction instructions.
    """

    redactions: list[Redaction] = field(default_factory=list)

    @property
    def total_redactions(self) -> int:
        """Total number of redaction instructions in the plan."""
        return len(self.redactions)

    def by_page(self, page_number: int) -> list[Redaction]:
        """Return only the redactions targeting a specific page.

        Args:
            page_number: The page number to filter by.

        Returns:
            Redactions that belong to *page_number*.
        """
        return [r for r in self.redactions if r.page_number == page_number]

    def by_type(self, detection_type: str) -> list[Redaction]:
        """Return only the redactions for a specific detection type.

        Args:
            detection_type: The detection type to filter by (e.g. ``"PAN"``).

        Returns:
            Redactions matching *detection_type*.
        """
        return [r for r in self.redactions if r.detection.detection_type == detection_type]


class RedactionPlanner:
    """Converts a list of detections into a structured redaction plan.

    The planner maps each detection to a redaction instruction using a
    configurable default redaction type and replacement text.
    """

    DEFAULT_REPLACEMENT = "*****"

    def plan(
        self,
        document: Document,
        detections: list[Detection],
        *,
        default_type: RedactionType = RedactionType.REPLACE,
    ) -> RedactionPlan:
        """Build a redaction plan from the given document and detections.

        Args:
            document: The source document (used for page/block lookup).
            detections: The fused list of detections to redact.
            default_type: Default redaction type to apply.

        Returns:
            A RedactionPlan with one entry per detection.
        """
        redactions: list[Redaction] = []
        for detection in detections:
            replacement = (
                detection.text
                if default_type == RedactionType.HIGHLIGHT
                else self.DEFAULT_REPLACEMENT
            )
            redactions.append(
                Redaction(
                    detection=detection,
                    redaction_type=default_type,
                    replacement_text=replacement,
                    page_number=detection.page_number,
                    span=detection.span,
                    bbox=detection.bbox,
                )
            )

        return RedactionPlan(redactions=redactions)

    @staticmethod
    def plan_with_replacement(
        document: Document,
        detections: list[Detection],
        *,
        replacement_text: str = DEFAULT_REPLACEMENT,
    ) -> RedactionPlan:
        """Build a plan using the ``REPLACE`` type with a custom replacement.

        Args:
            document: The source document.
            detections: The fused list of detections to redact.
            replacement_text: The replacement string (default ``[REDACTED]``).

        Returns:
            A RedactionPlan with ``REPLACE`` redactions.
        """
        planner = RedactionPlanner()
        return planner.plan(
            document,
            detections,
            default_type=RedactionType.REPLACE,
        )

    @staticmethod
    def plan_with_black_bar(
        document: Document,
        detections: list[Detection],
    ) -> RedactionPlan:
        """Build a plan using the ``BLACK_BAR`` type for every detection.

        Args:
            document: The source document.
            detections: The fused list of detections to redact.

        Returns:
            A RedactionPlan with ``BLACK_BAR`` redactions.
        """
        planner = RedactionPlanner()
        return planner.plan(
            document,
            detections,
            default_type=RedactionType.BLACK_BAR,
        )

    @staticmethod
    def plan_with_highlight(
        document: Document,
        detections: list[Detection],
    ) -> RedactionPlan:
        """Build a plan using the ``HIGHLIGHT`` type (no actual redaction).

        Args:
            document: The source document.
            detections: The fused list of detections to highlight.

        Returns:
            A RedactionPlan with ``HIGHLIGHT`` redactions.
        """
        planner = RedactionPlanner()
        return planner.plan(
            document,
            detections,
            default_type=RedactionType.HIGHLIGHT,
        )
