from __future__ import annotations

import re

from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import Span

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
"""Regex matching standard email addresses per RFC 5322 simplified."""


class EmailDetector(BaseDetector):
    """Detector that identifies email addresses in document text."""

    @property
    def name(self) -> str:
        """Human-readable detector name."""
        return "email"

    def scan(self, document: Document, *, values_only: bool = False) -> list[Detection]:
        """Scan a document for email addresses.

        Iterates over all text blocks, matches against EMAIL_PATTERN, and
        validates each candidate before yielding a Detection.

        Args:
            document: The document to scan.
            values_only: If ``True``, use per-span bounding boxes for
                precise value-only redaction.

        Returns:
            A list of Detection objects for each valid email address found.
        """
        detections: list[Detection] = []

        for page in document.pages:
            for block in page.blocks:
                if not isinstance(block, TextBlock):
                    continue

                for match in EMAIL_PATTERN.finditer(block.text):
                    email = match.group()
                    if not self._validate_format(email):
                        continue

                    match_bbox = (
                        block.bbox_for_span(match.start(), match.end())
                        if values_only
                        else block.bbox
                    )

                    detections.append(
                        Detection(
                            detector_name=self.name,
                            detection_type="EMAIL",
                            text=email,
                            span=Span(start=match.start(), end=match.end()),
                            bbox=match_bbox,
                            page_number=page.page_number,
                            confidence=0.9,
                        )
                    )

        return detections

    @staticmethod
    def _validate_format(email: str) -> bool:
        """Validate an email address against length and structural rules.

        Args:
            email: The email address string to validate.

        Returns:
            True if the email is structurally valid, False otherwise.
        """
        if len(email) > 254:
            return False
        local, _, domain = email.partition("@")
        if not local or len(local) > 64:
            return False
        if not domain or ".." in domain:
            return False
        return True
