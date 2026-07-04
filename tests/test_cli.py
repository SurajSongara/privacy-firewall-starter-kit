from typer.testing import CliRunner

from privacy_firewall.__main__ import app

runner = CliRunner()


def test_help_succeeds() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Offline-first PII Detection & Redaction Engine" in result.stdout


def test_version_succeeds() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"
