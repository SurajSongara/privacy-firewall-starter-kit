"""Tests for the review-plan CLI workflow (detect --plan / redact --plan)."""

from pathlib import Path

import fitz
from typer.testing import CliRunner

from privacy_firewall.__main__ import app
from privacy_firewall.engine.decision import ReviewDecision, ReviewPlan, SuggestedAction

runner = CliRunner()


def _write_pdf(path: Path, lines: list[str]) -> None:
    doc = fitz.open()
    page = doc.new_page()
    y = 100
    for line in lines:
        page.insert_text((50, y), line, fontsize=12)
        y += 30
    doc.save(str(path))
    doc.close()


def _make_plan(tmp_path: Path, name: str = "doc") -> tuple[Path, Path]:
    """Create a PII PDF and a review plan for it; return (pdf, plan) paths."""
    pdf = tmp_path / f"{name}.pdf"
    # PAN → confident redact suggestion; unknown UPI handle → 0.7 → ask band
    _write_pdf(pdf, ["PAN: AAAAA1111A", "UPI: someone@unknownhandle"])
    plan = tmp_path / f"{name}.plan.json"
    result = runner.invoke(app, ["detect", str(pdf), "--plan", str(plan)])
    assert result.exit_code == 0, result.stdout
    return pdf, plan


class TestDetectPlan:
    def test_writes_plan_with_suggestions(self, tmp_path: Path) -> None:
        pdf, plan_path = _make_plan(tmp_path)
        review_plan = ReviewPlan.model_validate_json(plan_path.read_text())
        assert review_plan.policy_name == "share-with-ai"
        assert review_plan.source_path == str(pdf)
        suggestions = {
            e.detection.detection_type: e.suggested_action for e in review_plan.entries
        }
        assert suggestions["PAN"] == SuggestedAction.REDACT
        assert suggestions["UPI"] == SuggestedAction.ASK

    def test_policy_option(self, tmp_path: Path) -> None:
        pdf = tmp_path / "doc.pdf"
        _write_pdf(pdf, ["PAN: AAAAA1111A"])
        plan_path = tmp_path / "plan.json"
        result = runner.invoke(
            app, ["detect", str(pdf), "--plan", str(plan_path), "--policy", "kyc"]
        )
        assert result.exit_code == 0
        review_plan = ReviewPlan.model_validate_json(plan_path.read_text())
        assert review_plan.entries[0].suggested_action == SuggestedAction.KEEP

    def test_unknown_policy_fails(self, tmp_path: Path) -> None:
        pdf = tmp_path / "doc.pdf"
        _write_pdf(pdf, ["PAN: AAAAA1111A"])
        result = runner.invoke(
            app, ["detect", str(pdf), "--plan", str(tmp_path / "p.json"), "--policy", "nope"]
        )
        assert result.exit_code != 0


class TestRedactPlan:
    def test_yes_applies_suggestions(self, tmp_path: Path) -> None:
        pdf, plan_path = _make_plan(tmp_path)
        out = tmp_path / "out.pdf"
        result = runner.invoke(
            app, ["redact", str(pdf), str(out), "--plan", str(plan_path), "--yes"]
        )
        assert result.exit_code == 0, result.stdout
        assert out.exists()
        # PAN (redact) + UPI (unresolved ask → redacted, privacy-first)
        assert "Redactions applied: 2" in result.stdout

    def test_undecided_without_yes_fails_with_hint(self, tmp_path: Path) -> None:
        pdf, plan_path = _make_plan(tmp_path)
        out = tmp_path / "out.pdf"
        result = runner.invoke(app, ["redact", str(pdf), str(out), "--plan", str(plan_path)])
        assert result.exit_code == 1
        assert not out.exists()

    def test_hash_mismatch_rejected(self, tmp_path: Path) -> None:
        _, plan_path = _make_plan(tmp_path)
        other_pdf = tmp_path / "other.pdf"
        _write_pdf(other_pdf, ["Different content entirely"])
        out = tmp_path / "out.pdf"
        result = runner.invoke(
            app, ["redact", str(other_pdf), str(out), "--plan", str(plan_path), "--yes"]
        )
        assert result.exit_code != 0
        assert not out.exists()

    def test_interactive_keep_persists_decision(self, tmp_path: Path) -> None:
        pdf, plan_path = _make_plan(tmp_path)
        out = tmp_path / "out.pdf"
        result = runner.invoke(
            app,
            ["redact", str(pdf), str(out), "--plan", str(plan_path), "--interactive"],
            input="k\n",
        )
        assert result.exit_code == 0, result.stdout
        # Only the PAN is redacted; the UPI ask entry was kept
        assert "Redactions applied: 1" in result.stdout
        saved = ReviewPlan.model_validate_json(plan_path.read_text())
        upi_entry = next(
            e for e in saved.entries if e.detection.detection_type == "UPI"
        )
        assert upi_entry.decision == ReviewDecision.KEEP

    def test_interactive_redact_all(self, tmp_path: Path) -> None:
        pdf, plan_path = _make_plan(tmp_path)
        out = tmp_path / "out.pdf"
        result = runner.invoke(
            app,
            ["redact", str(pdf), str(out), "--plan", str(plan_path), "--interactive"],
            input="R\n",
        )
        assert result.exit_code == 0, result.stdout
        assert "Redactions applied: 2" in result.stdout
