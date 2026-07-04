"""Abstract base class for OCR providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from privacy_firewall.models.document import Document


class OCRProvider(ABC):
    """Abstract interface for OCR engines.

    Every concrete OCR adapter must define a ``name`` class attribute
    and implement **both** ``process`` and ``process_bytes``, returning
    a ``Document`` whose pages contain ``TextBlock`` / ``ImageBlock``
    items with bounding boxes and confidence scores.
    """

    name: str = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Ensure every concrete subclass defines a non-empty ``name``."""
        super().__init_subclass__(**kwargs)
        if not cls.name:
            msg = f"{cls.__name__} must define a non-empty 'name' class attribute"
            raise TypeError(msg)

    @abstractmethod
    def process(self, path: str | Path) -> Document:
        """Run OCR on a PDF file on disk.

        Args:
            path: Path to the PDF file.

        Returns:
            A ``Document`` with OCR-extracted blocks.
        """

    @abstractmethod
    def process_bytes(self, data: bytes) -> Document:
        """Run OCR on PDF content from raw bytes.

        Args:
            data: Raw PDF bytes.

        Returns:
            A ``Document`` with OCR-extracted blocks.
        """
