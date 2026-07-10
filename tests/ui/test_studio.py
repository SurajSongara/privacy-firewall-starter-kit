"""Tests for the Studio dashboard (requires the ui extra + httpx)."""

from pathlib import Path

import fitz
import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from privacy_firewall.ui.studio import create_studio_app  # noqa: E402


def _make_pdf(path: Path, text: str = "PAN: AAAAA1111A") -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), text, fontsize=12)
    doc.save(str(path))
    doc.close()


@pytest.fixture
def studio(tmp_path: Path) -> TestClient:
    _make_pdf(tmp_path / "statement.pdf")
    _make_pdf(tmp_path / "invoice.pdf", "Email: user@example.com")
    return TestClient(create_studio_app(tmp_path))


class TestStudioDashboard:
    def test_index_serves_dashboard(self, studio: TestClient) -> None:
        response = studio.get("/")
        assert response.status_code == 200
        assert "Studio" in response.text

    def test_lists_workspace_pdfs(self, studio: TestClient) -> None:
        docs = studio.get("/api/documents").json()["documents"]
        names = {d["name"] for d in docs}
        assert names == {"statement.pdf", "invoice.pdf"}
        for d in docs:
            assert d["size"] > 0
            assert d["modified"] > 0
            assert d["id"]

    def test_excludes_redacted_outputs(self, studio: TestClient, tmp_path: Path) -> None:
        _make_pdf(tmp_path / "statement.redacted.pdf", "redacted")
        docs = studio.get("/api/documents").json()["documents"]
        assert all(not d["name"].endswith(".redacted.pdf") for d in docs)

    def test_upload_appears_in_list(self, studio: TestClient, tmp_path: Path) -> None:
        # Build the upload in a separate folder so it doesn't already exist
        # in the workspace (which would trigger the de-collision rename).
        src = tmp_path / "src"
        src.mkdir()
        _make_pdf(src / "uploaded.pdf", "Phone: 9876543210")
        with open(src / "uploaded.pdf", "rb") as fh:
            response = studio.post(
                "/api/upload", files={"file": ("uploaded.pdf", fh, "application/pdf")}
            )
        assert response.status_code == 200
        doc_id = response.json()["id"]
        names = {d["name"] for d in studio.get("/api/documents").json()["documents"]}
        assert "uploaded.pdf" in names
        assert doc_id

    def test_upload_rejects_non_pdf(self, studio: TestClient) -> None:
        response = studio.post(
            "/api/upload", files={"file": ("notes.txt", b"hello", "text/plain")}
        )
        assert response.status_code == 422


class TestStudioReviewMount:
    def test_review_page_served_under_doc_id(self, studio: TestClient) -> None:
        doc_id = studio.get("/api/documents").json()["documents"][0]["id"]
        response = studio.get(f"/review/{doc_id}/")
        assert response.status_code == 200
        assert "Privacy Firewall" in response.text

    def test_review_api_works_under_mount(self, studio: TestClient) -> None:
        docs = studio.get("/api/documents").json()["documents"]
        doc_id = next(d["id"] for d in docs if d["name"] == "statement.pdf")
        status = studio.get(f"/review/{doc_id}/api/status").json()
        assert status["status"] in {"ready", "starting", "parsing", "detecting", "ocr"}
        plan = studio.get(f"/review/{doc_id}/api/plan")
        if plan.status_code == 200:
            assert plan.json()["source"].endswith("statement.pdf")
