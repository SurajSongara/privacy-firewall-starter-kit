"""Tests for the ReviewSession (engine side of the review UI)."""

from pathlib import Path

import fitz
import pytest

from privacy_firewall.policy import BUILTIN_POLICIES
from privacy_firewall.ui.session import ReviewSession


@pytest.fixture
def pii_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "doc.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "PAN: AAAAA1111A", fontsize=12)
    page.insert_text((50, 140), "UPI: someone@unknownhandle", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def session(pii_pdf: Path) -> ReviewSession:
    return ReviewSession(pii_pdf, BUILTIN_POLICIES["share-with-ai"])


class TestReviewSession:
    def test_summary_shape(self, session: ReviewSession) -> None:
        summary = session.summary()
        assert summary["policy"] == "share-with-ai"
        assert summary["pages"][0]["page_number"] == 1
        assert summary["counts"]["redact"] >= 1
        types = {e["type"] for e in summary["entries"]}
        assert "PAN" in types
        assert "UPI" in types
        for entry in summary["entries"]:
            assert entry["detection_id"]
            assert entry["reasons"]
            assert entry["effective_action"] in ("redact", "keep", "ask")

    def test_set_decision(self, session: ReviewSession) -> None:
        entry_id = session.summary()["entries"][0]["detection_id"]
        assert session.set_decision(entry_id, "keep")
        updated = next(
            e for e in session.summary()["entries"] if e["detection_id"] == entry_id
        )
        assert updated["decision"] == "keep"
        assert updated["effective_action"] == "keep"
        assert session.set_decision(entry_id, None)
        assert not session.set_decision("bogus-id", "keep")

    def test_page_png_cached(self, session: ReviewSession) -> None:
        png1 = session.page_png(1)
        assert png1[:8] == b"\x89PNG\r\n\x1a\n"
        assert session.page_png(1) is png1

    def test_apply_writes_redacted_pdf_and_plan(self, session: ReviewSession) -> None:
        out_path, count = session.apply()
        assert out_path.exists()
        assert out_path.name == "doc.redacted.pdf"
        assert count >= 1
        assert session.plan_file_path.exists()
        # The redacted PDF must no longer contain the PAN
        with fitz.open(out_path) as doc:
            text = doc[0].get_text()
        assert "AAAAA1111A" not in text

    def test_apply_respects_keep_decisions(self, pii_pdf: Path) -> None:
        session = ReviewSession(pii_pdf, BUILTIN_POLICIES["share-with-ai"])
        for entry in session.summary()["entries"]:
            session.set_decision(entry["detection_id"], "keep")
        out_path, count = session.apply()
        assert count == 0
        with fitz.open(out_path) as doc:
            assert "AAAAA1111A" in doc[0].get_text()
