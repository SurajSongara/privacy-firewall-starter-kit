"""Abstract base class for bank-statement profilers."""
from __future__ import annotations

from abc import ABC, abstractmethod

from privacy_firewall.bank_profiler.models import BankProfile
from privacy_firewall.models.document import Document


class BankProfiler(ABC):
    """Identifies the bank and extracts metadata from a statement document.

    Subclasses **must** set a non-empty ``name`` class attribute.
    """

    name: str = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name:
            raise TypeError(f"{cls.__name__} must define a non-empty 'name' class attribute")

    @abstractmethod
    def profile(self, document: Document) -> BankProfile:
        """Analyse a document and return its bank profile.

        Args:
            document: The parsed document to profile.

        Returns:
            A ``BankProfile`` with the extracted metadata.
        """
        ...
