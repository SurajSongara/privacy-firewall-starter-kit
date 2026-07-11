"""Tests for workspace terms (remembered marks across documents)."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from privacy_firewall.policy.models import PolicyAction, TypePolicy
from privacy_firewall.policy.presets import BUILTIN_POLICIES
from privacy_firewall.ui.session import ReviewSession
from privacy_firewall.ui.terms import TermsStore, WorkspaceTerm


def _pdf(path: Path, *lines: str) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    y = 100
    for line in lines:
        page.insert_text((50, y), line, fontsize=12)
        y += 40
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


class TestTermsStore:
    def test_add_is_idempotent_and_persists(self, workspace: Path) -> None:
        store = TermsStore.for_workspace(workspace)
        assert store.add("Suraj", "name", added_from="a.pdf")
        assert not store.add("suraj", "NAME")  # case-folded identity
        reloaded = TermsStore.for_workspace(workspace)
        assert [t.label for t in reloaded.terms] == ["NAME"]
        assert reloaded.terms[0].added_from == "a.pdf"

    def test_remove(self, workspace: Path) -> None:
        store = TermsStore.for_workspace(workspace)
        store.add("Suraj", "NAME")
        assert store.remove("SURAJ", "NAME")
        assert not store.remove("SURAJ", "NAME")
        assert TermsStore.for_workspace(workspace).terms == []

    def test_ignore_hides_from_active_terms(self, workspace: Path) -> None:
        store = TermsStore.for_workspace(workspace)
        store.add("Suraj", "NAME")
        store.ignore("suraj", "NAME")
        assert store.active_terms() == []
        reloaded = TermsStore.for_workspace(workspace)
        assert reloaded.active_terms() == []
        assert len(reloaded.terms) == 1  # still stored, just allowlisted

    def test_re_adding_clears_allowlist(self, workspace: Path) -> None:
        store = TermsStore.for_workspace(workspace)
        store.add("Suraj", "NAME")
        store.ignore("Suraj", "NAME")
        store.add("Suraj", "NAME")
        assert [t.text for t in store.active_terms()] == ["Suraj"]

    def test_blank_term_raises(self, workspace: Path) -> None:
        store = TermsStore.for_workspace(workspace)
        with pytest.raises(ValueError, match="blank"):
            store.add("   ", "NAME")

    def test_corrupt_file_means_empty_store(self, workspace: Path) -> None:
        path = workspace / ".privacy-firewall" / "terms.json"
        path.parent.mkdir(parents=True)
        path.write_text("{ nope", encoding="utf-8")
        assert TermsStore(path).terms == []


class TestSessionWorkspaceMemory:
    def test_term_remembered_in_one_doc_suggested_in_another(self, workspace: Path) -> None:
        store = TermsStore.for_workspace(workspace)
        doc_a = _pdf(workspace / "a.pdf", "Author: Ramesh Kumar", "Contact soon")
        doc_b = _pdf(workspace / "b.pdf", "Reviewed by Ramesh Kumar today")

        first = ReviewSession(doc_a, BUILTIN_POLICIES["share-with-ai"], terms_store=store)
        assert first.mark_text("Ramesh Kumar", "NAME").added
        assert first.remember_text("Ramesh Kumar", "NAME")

        second = ReviewSession(doc_b, BUILTIN_POLICIES["share-with-ai"], terms_store=store)
        remembered = [e for e in second.plan.entries if e.detection.detector_name == "remembered"]
        assert len(remembered) == 1
        entry = remembered[0]
        assert entry.detection.detection_type == "NAME"
        assert entry.decision is None  # a suggestion, not a decision
        assert entry.suggested_action.value == "redact"

    def test_sync_picks_up_terms_added_after_pipeline(self, workspace: Path) -> None:
        store = TermsStore.for_workspace(workspace)
        doc = _pdf(workspace / "c.pdf", "Written by Ramesh Kumar")
        session = ReviewSession(doc, BUILTIN_POLICIES["share-with-ai"], terms_store=store)
        assert session.sync_remembered_terms() == 0
        store.add("Ramesh Kumar", "NAME")
        assert session.sync_remembered_terms() == 1
        assert session.sync_remembered_terms() == 0  # idempotent

    def test_ignored_terms_are_not_suggested(self, workspace: Path) -> None:
        store = TermsStore.for_workspace(workspace)
        store.add("Ramesh Kumar", "NAME")
        store.ignore("Ramesh Kumar", "NAME")
        doc = _pdf(workspace / "d.pdf", "Written by Ramesh Kumar")
        session = ReviewSession(doc, BUILTIN_POLICIES["share-with-ai"], terms_store=store)
        assert all(e.detection.detector_name != "remembered" for e in session.plan.entries)

    def test_forget_term_removes_entries_and_store_entry(self, workspace: Path) -> None:
        store = TermsStore.for_workspace(workspace)
        store.add("Ramesh Kumar", "NAME")
        doc = _pdf(workspace / "e.pdf", "Ramesh Kumar wrote this", "Ramesh Kumar signed")
        session = ReviewSession(doc, BUILTIN_POLICIES["share-with-ai"], terms_store=store)
        remembered = [e for e in session.plan.entries if e.detection.detector_name == "remembered"]
        assert len(remembered) == 2
        assert session.forget_term(remembered[0].detection_id)
        assert all(e.detection.detector_name != "remembered" for e in session.plan.entries)
        assert store.terms == []
        assert session.sync_remembered_terms() == 0  # gone for good

    def test_session_without_store_is_unaffected(self, workspace: Path) -> None:
        doc = _pdf(workspace / "f.pdf", "Ramesh Kumar wrote this")
        session = ReviewSession(doc, BUILTIN_POLICIES["share-with-ai"])
        assert session.sync_remembered_terms() == 0
        assert not session.remember_text("Ramesh Kumar", "NAME")
        assert session.summary()["workspace_terms"] is False

    def test_policy_keep_action_becomes_keep_suggestion(self, workspace: Path) -> None:
        store = TermsStore.for_workspace(workspace)
        store.add("Ramesh Kumar", "NAME")
        policy = BUILTIN_POLICIES["share-with-ai"].model_copy(
            update={
                "types": {
                    **BUILTIN_POLICIES["share-with-ai"].types,
                    "NAME": TypePolicy(action=PolicyAction.KEEP),
                }
            }
        )
        doc = _pdf(workspace / "g.pdf", "Ramesh Kumar wrote this")
        session = ReviewSession(doc, policy, terms_store=store)
        [entry] = [e for e in session.plan.entries if e.detection.detector_name == "remembered"]
        assert entry.suggested_action.value == "keep"


class TestWorkspaceTermModel:
    def test_key_is_casefolded(self) -> None:
        assert WorkspaceTerm("Suraj", "NAME").key == WorkspaceTerm("suraj", "NAME").key
