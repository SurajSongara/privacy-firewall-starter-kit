from pathlib import Path

import pytest

from privacy_firewall.engine.decision import (
    DecisionEngine,
    ReviewDecision,
    ReviewPlan,
    SuggestedAction,
    file_sha256,
)
from privacy_firewall.models.detection import Detection
from privacy_firewall.models.geometry import BoundingBox, Span
from privacy_firewall.policy import Policy, PolicyAction, TypePolicy


def _detection(
    detection_type: str = "PAN",
    text: str = "ABCDE1234F",
    confidence: float = 0.95,
    start: int = 0,
) -> Detection:
    return Detection(
        detector_name=detection_type.lower(),
        detection_type=detection_type,
        text=text,
        span=Span(start=start, end=start + len(text)),
        bbox=BoundingBox(x0=0.0, y0=0.0, x1=100.0, y1=20.0),
        page_number=1,
        confidence=confidence,
    )


def _plan(detections: list[Detection], policy: Policy) -> ReviewPlan:
    return DecisionEngine().decide(
        detections, policy, source_path="doc.pdf", source_sha256="abc123"
    )


REDACT_ALL = Policy(name="test-redact")


class TestSuggestions:
    def test_high_confidence_suggests_redact(self) -> None:
        plan = _plan([_detection(confidence=0.95)], REDACT_ALL)
        assert plan.entries[0].suggested_action == SuggestedAction.REDACT

    def test_mid_confidence_suggests_ask(self) -> None:
        plan = _plan([_detection(confidence=0.6)], REDACT_ALL)
        assert plan.entries[0].suggested_action == SuggestedAction.ASK

    def test_low_confidence_suggests_keep(self) -> None:
        plan = _plan([_detection(confidence=0.4)], REDACT_ALL)
        assert plan.entries[0].suggested_action == SuggestedAction.KEEP

    def test_keep_policy_wins_over_confidence(self) -> None:
        policy = Policy(
            name="keep-pan", types={"PAN": TypePolicy(action=PolicyAction.KEEP)}
        )
        plan = _plan([_detection(confidence=0.99)], policy)
        assert plan.entries[0].suggested_action == SuggestedAction.KEEP

    def test_ask_policy_always_asks(self) -> None:
        policy = Policy(name="ask-all", default_action=PolicyAction.ASK)
        plan = _plan([_detection(confidence=0.99)], policy)
        assert plan.entries[0].suggested_action == SuggestedAction.ASK

    def test_allowlisted_value_kept(self) -> None:
        policy = Policy(
            name="allow",
            types={"PHONE": TypePolicy(allow_values=("1800-11-2233",))},
        )
        plan = _plan(
            [_detection(detection_type="PHONE", text="1800-11-2233", confidence=0.95)],
            policy,
        )
        assert plan.entries[0].suggested_action == SuggestedAction.KEEP
        assert "allow-listed" in plan.entries[0].suggestion_reasons[0]

    def test_every_entry_has_reasons(self) -> None:
        plan = _plan([_detection(confidence=c) for c in (0.95, 0.6, 0.4)], REDACT_ALL)
        assert all(e.suggestion_reasons for e in plan.entries)

    def test_entries_sorted_by_page_and_span(self) -> None:
        d1 = _detection(start=50)
        d2 = _detection(start=0, text="FGHIJ5678K")
        plan = _plan([d1, d2], REDACT_ALL)
        assert [e.detection.span.start for e in plan.entries] == [0, 50]


class TestResolve:
    def test_resolve_with_all_decisions(self) -> None:
        plan = _plan(
            [_detection(confidence=0.95), _detection(confidence=0.6, start=20)], REDACT_ALL
        )
        plan.entries[0].decision = ReviewDecision.REDACT
        plan.entries[1].decision = ReviewDecision.KEEP
        redacted = plan.resolve()
        assert len(redacted) == 1
        assert redacted[0] == plan.entries[0].detection

    def test_resolve_undecided_raises(self) -> None:
        plan = _plan([_detection()], REDACT_ALL)
        with pytest.raises(ValueError, match="no decision"):
            plan.resolve()

    def test_accept_suggestions_redacts_ask_entries(self) -> None:
        # Privacy-first: an unresolved "ask" under --yes is redacted.
        plan = _plan(
            [
                _detection(confidence=0.95),
                _detection(confidence=0.6, start=20),
                _detection(confidence=0.4, start=40),
            ],
            REDACT_ALL,
        )
        redacted = plan.resolve(accept_suggestions=True)
        assert len(redacted) == 2  # redact + ask; keep stays

    def test_user_decision_overrides_suggestion(self) -> None:
        plan = _plan([_detection(confidence=0.95)], REDACT_ALL)
        plan.entries[0].decision = ReviewDecision.KEEP
        assert plan.resolve(accept_suggestions=True) == []

    def test_counts(self) -> None:
        plan = _plan(
            [
                _detection(confidence=0.95),
                _detection(confidence=0.6, start=20),
                _detection(confidence=0.4, start=40),
            ],
            REDACT_ALL,
        )
        assert plan.counts() == {"redact": 1, "ask": 1, "keep": 1}
        plan.entries[1].decision = ReviewDecision.KEEP
        assert plan.counts() == {"redact": 1, "ask": 0, "keep": 2}


class TestSerialization:
    def test_json_round_trip(self) -> None:
        plan = _plan([_detection(confidence=0.6)], REDACT_ALL)
        plan.entries[0].decision = ReviewDecision.REDACT
        restored = ReviewPlan.model_validate_json(plan.model_dump_json())
        assert restored.source_sha256 == "abc123"
        assert restored.policy_name == "test-redact"
        assert restored.entries[0].decision == ReviewDecision.REDACT
        assert restored.entries[0].detection_id == plan.entries[0].detection_id
        assert restored.entries[0].detection == plan.entries[0].detection

    def test_entry_by_id(self) -> None:
        plan = _plan([_detection()], REDACT_ALL)
        entry = plan.entries[0]
        assert plan.entry_by_id(entry.detection_id) is entry
        assert plan.entry_by_id("nope") is None

    def test_pending_entries(self) -> None:
        plan = _plan(
            [_detection(confidence=0.95), _detection(confidence=0.6, start=20)],
            REDACT_ALL,
        )
        assert len(plan.pending_entries()) == 1
        plan.entries[1].decision = ReviewDecision.KEEP
        assert plan.pending_entries() == []


class TestFileHash:
    def test_file_sha256(self, tmp_path: Path) -> None:
        f = tmp_path / "x.bin"
        f.write_bytes(b"hello")
        assert file_sha256(f) == (
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )
