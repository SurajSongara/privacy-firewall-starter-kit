import pytest

from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document


class _ConcreteDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "test_detector"

    def scan(self, document: Document) -> list[Detection]:
        return []


class TestBaseDetector:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            BaseDetector()  # type: ignore[abstract]

    def test_concrete_detector(self) -> None:
        detector = _ConcreteDetector()
        assert detector.name == "test_detector"
        assert detector.scan(Document()) == []
