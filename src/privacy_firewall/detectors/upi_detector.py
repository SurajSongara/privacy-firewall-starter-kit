from __future__ import annotations

import re

from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document
from privacy_firewall.models.geometry import Span

UPI_PATTERN = re.compile(r"[a-zA-Z0-9._-]+@[a-zA-Z][a-zA-Z0-9._-]*")

KNOWN_UPI_HANDLES: frozenset[str] = frozenset(
    {
        "ybl",
        "paytm",
        "sbi",
        "okicici",
        "okhdfcbank",
        "okaxis",
        "axl",
        "apl",
        "ibibo",
        "freecharge",
        "phonepe",
        "upi",
        "cred",
        "mobikwik",
        "pnb",
        "yesbank",
        "icici",
        "hdfcbank",
        "idfc",
        "kotak",
        "indus",
        "unionbankofindia",
        "canarabank",
        "boi",
        "barodaupi",
        "rbl",
        "federal",
    }
)


class UpiDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "upi"

    def scan(self, document: Document) -> list[Detection]:
        detections: list[Detection] = []

        for page in document.pages:
            for block in page.blocks:
                if not isinstance(block, TextBlock):
                    continue

                for match in UPI_PATTERN.finditer(block.text):
                    upi_id = match.group()
                    if not self._validate_format(upi_id):
                        continue
                    if self._is_duplicate(detections, upi_id):
                        continue

                    detections.append(
                        Detection(
                            detector_name=self.name,
                            detection_type="UPI",
                            text=upi_id,
                            span=Span(start=match.start(), end=match.end()),
                            bbox=block.bbox,
                            page_number=page.page_number,
                            confidence=self._resolve_confidence(upi_id),
                        )
                    )

        return detections

    @staticmethod
    def _validate_format(upi_id: str) -> bool:
        if len(upi_id) > 50:
            return False
        if ".." in upi_id or "@@" in upi_id:
            return False
        parts = upi_id.split("@")
        if len(parts) != 2:
            return False
        local, handle = parts
        if not local or not handle:
            return False
        if "." in handle:
            return False
        return True

    @staticmethod
    def _resolve_confidence(upi_id: str) -> float:
        handle = upi_id.split("@", 1)[1] if "@" in upi_id else ""
        if handle in KNOWN_UPI_HANDLES:
            return 0.95
        return 0.7

    @staticmethod
    def _is_duplicate(detections: list[Detection], upi_id: str) -> bool:
        return any(d.text == upi_id for d in detections)
