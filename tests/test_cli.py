"""Tests for the privacy-firewall CLI commands."""

import fitz
from typer.testing import CliRunner

from privacy_firewall.__main__ import app

runner = CliRunner()


def _make_pdf(text: str = "Hello World") -> bytes:
    """Generate a one-page PDF with the given text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), text, fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def _make_pii_pdf() -> bytes:
    """Generate a PDF with PII-like data for detection testing."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "PAN: AAAAA1111A", fontsize=12)
    page.insert_text((50, 150), "Email: user@example.com", fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


# --- Global flags ---


def test_help_succeeds() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Offline-first PII Detection & Redaction Engine" in result.stdout


def test_version_succeeds() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


# --- scan command ---


def test_scan_help() -> None:
    result = runner.invoke(app, ["scan", "--help"])
    assert result.exit_code == 0
    assert "scan" in result.stdout


def test_scan_shows_pages(tmp_path: str) -> None:
    pdf = _make_pdf()
    path = f"{tmp_path}/test.pdf"
    with open(path, "wb") as f:
        f.write(pdf)
    result = runner.invoke(app, ["scan", path])
    assert result.exit_code == 0
    assert "Pages: 1" in result.stdout


def test_scan_shows_text_blocks(tmp_path: str) -> None:
    pdf = _make_pdf("My PAN is ABCDE1234F")
    path = f"{tmp_path}/test.pdf"
    with open(path, "wb") as f:
        f.write(pdf)
    result = runner.invoke(app, ["scan", path])
    assert result.exit_code == 0
    assert "TextBlock" in result.stdout
    assert "ABCDE1234F" in result.stdout


def test_scan_rejects_missing_file() -> None:
    result = runner.invoke(app, ["scan", "nonexistent.pdf"])
    assert result.exit_code != 0


# --- detect command ---


def test_detect_help() -> None:
    result = runner.invoke(app, ["detect", "--help"])
    assert result.exit_code == 0
    assert "detect" in result.stdout


def test_detect_finds_pii(tmp_path: str) -> None:
    pdf = _make_pii_pdf()
    path = f"{tmp_path}/test.pdf"
    with open(path, "wb") as f:
        f.write(pdf)
    result = runner.invoke(app, ["detect", path])
    assert result.exit_code == 0
    assert "Detections" in result.stdout
    assert "PAN" in result.stdout or "EMAIL" in result.stdout


def test_detect_with_specific_detector(tmp_path: str) -> None:
    pdf = _make_pii_pdf()
    path = f"{tmp_path}/test.pdf"
    with open(path, "wb") as f:
        f.write(pdf)
    result = runner.invoke(app, ["detect", path, "--detector", "pan"])
    assert result.exit_code == 0
    assert "PAN" in result.stdout
    assert "EMAIL" not in result.stdout


def test_detect_no_fuse_flag(tmp_path: str) -> None:
    pdf = _make_pii_pdf()
    path = f"{tmp_path}/test.pdf"
    with open(path, "wb") as f:
        f.write(pdf)
    result = runner.invoke(app, ["detect", path, "--no-fuse"])
    assert result.exit_code == 0


def test_detect_unknown_detector_fails(tmp_path: str) -> None:
    pdf = _make_pdf()
    path = f"{tmp_path}/test.pdf"
    with open(path, "wb") as f:
        f.write(pdf)
    result = runner.invoke(app, ["detect", path, "--detector", "unknown"])
    assert result.exit_code != 0
    error_msg = result.stdout + result.stderr
    assert "Unknown detector" in error_msg


def test_detect_rejects_missing_file() -> None:
    result = runner.invoke(app, ["detect", "nonexistent.pdf"])
    assert result.exit_code != 0


# --- redact command ---


def test_redact_help() -> None:
    result = runner.invoke(app, ["redact", "--help"])
    assert result.exit_code == 0
    assert "redact" in result.stdout


def test_redact_creates_output(tmp_path: str) -> None:
    pdf = _make_pii_pdf()
    input_path = f"{tmp_path}/input.pdf"
    output_path = f"{tmp_path}/output.pdf"
    with open(input_path, "wb") as f:
        f.write(pdf)
    result = runner.invoke(app, ["redact", input_path, output_path])
    assert result.exit_code == 0
    assert "Redacted PDF saved to" in result.stdout
    assert "Redactions applied" in result.stdout
    import os
    assert os.path.exists(output_path)


def test_redact_with_highlight_type(tmp_path: str) -> None:
    pdf = _make_pii_pdf()
    input_path = f"{tmp_path}/input.pdf"
    output_path = f"{tmp_path}/output.pdf"
    with open(input_path, "wb") as f:
        f.write(pdf)
    result = runner.invoke(app, ["redact", input_path, output_path, "--type", "highlight"])
    assert result.exit_code == 0
    assert "Redacted PDF saved to" in result.stdout


def test_redact_with_black_bar_type(tmp_path: str) -> None:
    pdf = _make_pii_pdf()
    input_path = f"{tmp_path}/input.pdf"
    output_path = f"{tmp_path}/output.pdf"
    with open(input_path, "wb") as f:
        f.write(pdf)
    result = runner.invoke(app, ["redact", input_path, output_path, "--type", "black-bar"])
    assert result.exit_code == 0
    assert "Redacted PDF saved to" in result.stdout


def test_redact_unknown_type_fails(tmp_path: str) -> None:
    pdf = _make_pii_pdf()
    input_path = f"{tmp_path}/input.pdf"
    output_path = f"{tmp_path}/output.pdf"
    with open(input_path, "wb") as f:
        f.write(pdf)
    result = runner.invoke(app, ["redact", input_path, output_path, "--type", "invalid"])
    assert result.exit_code != 0
    error_msg = result.stdout + result.stderr
    assert "Unknown redaction type" in error_msg


def test_redact_with_specific_detector(tmp_path: str) -> None:
    pdf = _make_pii_pdf()
    input_path = f"{tmp_path}/input.pdf"
    output_path = f"{tmp_path}/output.pdf"
    with open(input_path, "wb") as f:
        f.write(pdf)
    result = runner.invoke(app, ["redact", input_path, output_path, "--detector", "pan"])
    assert result.exit_code == 0
    # Only PAN detected, so redactions should be 1
    assert "Redactions applied: 1" in result.stdout
