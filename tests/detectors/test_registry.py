from privacy_firewall.detectors.base import BaseDetector
from privacy_firewall.detectors.registry import DetectorRegistry
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document


class _PanDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "pan"

    def scan(self, document: Document, *, values_only: bool = False) -> list[Detection]:
        return []


class _AadhaarDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "aadhaar"

    def scan(self, document: Document, *, values_only: bool = False) -> list[Detection]:
        return []


class TestDetectorRegistry:
    def test_empty(self) -> None:
        registry = DetectorRegistry()
        assert registry.detector_names == []

    def test_register(self) -> None:
        registry = DetectorRegistry()
        registry.register(_PanDetector())
        assert registry.detector_names == ["pan"]

    def test_register_multiple(self) -> None:
        registry = DetectorRegistry()
        registry.register(_PanDetector())
        registry.register(_AadhaarDetector())
        assert set(registry.detector_names) == {"pan", "aadhaar"}

    def test_get(self) -> None:
        registry = DetectorRegistry()
        registry.register(_PanDetector())
        detector = registry.get("pan")
        assert detector is not None
        assert detector.name == "pan"

    def test_get_missing(self) -> None:
        registry = DetectorRegistry()
        assert registry.get("missing") is None

    def test_unregister(self) -> None:
        registry = DetectorRegistry()
        registry.register(_PanDetector())
        registry.unregister("pan")
        assert registry.detector_names == []

    def test_run_all_empty(self) -> None:
        registry = DetectorRegistry()
        result = registry.run_all(Document())
        assert result.total_detections == 0

    def test_run_all_with_detectors(self) -> None:
        registry = DetectorRegistry()
        registry.register(_PanDetector())
        registry.register(_AadhaarDetector())
        result = registry.run_all(Document())
        assert result.total_detections == 0
        assert set(result.detectors_run) == {"pan", "aadhaar"}

    def test_run_specific(self) -> None:
        registry = DetectorRegistry()
        registry.register(_PanDetector())
        result = registry.run(Document(), "pan")
        assert result is not None
        assert result.detectors_run == ["pan"]

    def test_run_missing(self) -> None:
        registry = DetectorRegistry()
        result = registry.run(Document(), "missing")
        assert result is None

    def test_detectors_property(self) -> None:
        registry = DetectorRegistry()
        registry.register(_PanDetector())
        dets = registry.detectors
        assert "pan" in dets
        assert isinstance(dets["pan"], BaseDetector)
