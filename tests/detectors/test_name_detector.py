"""Tests for the evidence-based NAME detector."""

from __future__ import annotations

from privacy_firewall.detectors.name_detector import NameDetector
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox


def _document(*block_texts: str) -> Document:
    blocks = [
        TextBlock(
            block_id=f"b{i}",
            bbox=BoundingBox(x0=0.0, y0=float(i * 30), x1=400.0, y1=float(i * 30 + 20)),
            page_number=1,
            confidence=1.0,
            text=text,
        )
        for i, text in enumerate(block_texts)
    ]
    return Document(pages=[Page(page_number=1, width=612.0, height=792.0, blocks=blocks)])


RESUME_BLOCKS = (
    "Suraj Songara",
    "+91-9981663005 | suraj.songara.work@gmail.com | linkedin.com/in/surajsongara",
    "github.com/SurajSongara | B.Tech CS",
    "## 1. SurajSongara_DE_v1.pdf",
    "Experienced engineer building data platforms.",
)


class TestNameDetector:
    def setup_method(self) -> None:
        self.detector = NameDetector()

    def _texts(self, detections: list[Detection]) -> set[str]:
        return {d.text.casefold() for d in detections}

    def test_corroborated_tokens_detected_everywhere(self) -> None:
        doc = _document(*RESUME_BLOCKS)
        detections = self.detector.scan(doc)
        texts = self._texts(detections)
        assert "suraj" in texts
        assert "songara" in texts
        # inside the filename token too (camel boundary in block 3)
        filename_block_hits = [
            d
            for d in detections
            if "SurajSongara_DE_v1.pdf" in RESUME_BLOCKS[3] and d.span.start < len(RESUME_BLOCKS[3])
        ]
        assert filename_block_hits

    def test_corroborated_tokens_are_high_confidence(self) -> None:
        detections = self.detector.scan(_document(*RESUME_BLOCKS))
        for d in detections:
            if d.text.casefold() in ("suraj", "songara"):
                assert d.confidence == 0.9, d.text

    def test_email_only_evidence_is_ask_band(self) -> None:
        doc = _document("Reach out: priya.patel@example.com for details")
        detections = self.detector.scan(doc)
        texts = self._texts(detections)
        assert "priya" in texts
        assert "patel" in texts
        assert all(d.confidence == 0.6 for d in detections)

    def test_title_line_alone_never_detects(self) -> None:
        doc = _document(
            "State Bank Of India",
            "Account statement for 2026",
            "UTR: 7987465071 | Ref ID: 8223027920",
            "Branch Code: 30524@sbi.coin",
        )
        assert self.detector.scan(doc) == []

    def test_numeric_email_local_gives_no_candidates(self) -> None:
        doc = _document("System mail: 30524@sbi.co.in")
        assert self.detector.scan(doc) == []

    def test_no_match_inside_lowercase_word(self) -> None:
        # "rama" derived from an email must not match inside "panorama"
        doc = _document("rama.krishnan@example.com wrote about the panorama view")
        detections = self.detector.scan(doc)
        for d in detections:
            assert d.text.casefold() != "rama" or "panorama" not in d.text

    def test_stopword_locals_ignored(self) -> None:
        doc = _document("Contact info@example.com or support@example.com")
        assert self.detector.scan(doc) == []

    def test_short_tokens_ignored(self) -> None:
        doc = _document("Contact raj.k@example.com now")  # both fragments < 4 chars
        assert self.detector.scan(doc) == []

    def test_camel_handle_alone_is_ask_band(self) -> None:
        doc = _document("Find me at github.com/PriyaPatel")
        detections = self.detector.scan(doc)
        assert detections
        assert {d.confidence for d in detections} == {0.6}

    def test_values_only_narrows_bbox(self) -> None:
        doc = _document(*RESUME_BLOCKS)
        wide = self.detector.scan(doc, values_only=False)
        narrow = self.detector.scan(doc, values_only=True)
        assert len(wide) == len(narrow)
        # every values-only bbox fits inside its block-level counterpart
        for w, n in zip(wide, narrow):
            assert n.bbox.x1 - n.bbox.x0 <= w.bbox.x1 - w.bbox.x0

    def test_longer_match_swallows_contained_tokens(self) -> None:
        doc = _document(
            "suraj.songara.work@gmail.com",
            "linkedin.com/in/surajsongara",
        )
        detections = self.detector.scan(doc)
        # in the handle URL, "surajsongara" wins over "suraj"/"songara"
        handle_hits = [d for d in detections if d.text.casefold() == "surajsongara"]
        assert handle_hits
        handle_block = "linkedin.com/in/surajsongara"
        slug_start = handle_block.index("surajsongara")
        inside_handle = [
            d
            for d in detections
            if d.text.casefold() in ("suraj", "songara")
            and slug_start <= d.span.start < slug_start + len("surajsongara")
            and d.span.end <= slug_start + len("surajsongara")
            # same block: the email block also has these tokens at low offsets
            and d.span.start >= slug_start
        ]
        assert inside_handle == []
