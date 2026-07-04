from __future__ import annotations

from abc import ABC, abstractmethod

from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document


class BaseDetector(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def scan(self, document: Document) -> list[Detection]: ...
