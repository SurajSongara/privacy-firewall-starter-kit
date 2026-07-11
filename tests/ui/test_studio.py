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

    def test_upload_rejects_unsupported_type(self, studio: TestClient) -> None:
        response = studio.post(
            "/api/upload", files={"file": ("archive.zip", b"PK\x03\x04", "application/zip")}
        )
        assert response.status_code == 422
        assert "Unsupported file type" in response.text

    def test_upload_rejects_fake_pdf(self, studio: TestClient) -> None:
        response = studio.post(
            "/api/upload", files={"file": ("fake.pdf", b"hello", "application/pdf")}
        )
        assert response.status_code == 422

    def test_upload_rejects_oversized_file(
        self, studio: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from privacy_firewall.ui import studio as studio_module

        monkeypatch.setattr(studio_module, "MAX_UPLOAD_BYTES", 1024)
        response = studio.post(
            "/api/upload",
            files={"file": ("big.pdf", b"%PDF" + b"x" * 2048, "application/pdf")},
        )
        assert response.status_code == 413
        assert "upload limit" in response.text

    def test_upload_rejects_empty_file(self, studio: TestClient) -> None:
        response = studio.post("/api/upload", files={"file": ("empty.pdf", b"", "application/pdf")})
        assert response.status_code == 422
        assert "empty" in response.text

    def test_documents_report_pipeline_status(self, studio: TestClient) -> None:
        docs = studio.get("/api/documents").json()["documents"]
        assert docs
        for d in docs:
            assert "status" in d
            assert "error" in d


def _wait_ready(studio: TestClient, doc_id: str, timeout: float = 30.0) -> None:
    """Poll a mounted review's status until the pipeline is ready."""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = studio.get(f"/review/{doc_id}/api/status").json()["status"]
        if status == "ready":
            return
        if status == "error":
            pytest.fail(f"pipeline errored for {doc_id}")
        time.sleep(0.2)
    pytest.fail(f"pipeline for {doc_id} not ready within {timeout}s")


class TestStudioMultiFormat:
    def test_upload_txt_is_converted_and_reviewable(
        self, studio: TestClient, tmp_path: Path
    ) -> None:
        payload = b"Customer phone: 9876543210\nEmail: someone@example.com\n"
        response = studio.post("/api/upload", files={"file": ("notes.txt", payload, "text/plain")})
        assert response.status_code == 200
        doc_id = response.json()["id"]

        docs = studio.get("/api/documents").json()["documents"]
        entry = next(d for d in docs if d["id"] == doc_id)
        assert entry["name"] == "notes.txt"
        assert entry["type"] == "txt"

        _wait_ready(studio, doc_id)
        plan = studio.get(f"/review/{doc_id}/api/plan").json()
        texts = {e["text"] for e in plan["entries"]}
        assert "someone@example.com" in texts

    def test_upload_markdown_accepted(self, studio: TestClient) -> None:
        response = studio.post(
            "/api/upload",
            files={"file": ("readme.md", b"# Notes\nPAN: ABCPE1234F", "text/markdown")},
        )
        assert response.status_code == 200
        doc_id = response.json()["id"]
        _wait_ready(studio, doc_id)
        plan = studio.get(f"/review/{doc_id}/api/plan").json()
        assert any(e["text"] == "ABCPE1234F" for e in plan["entries"])

    def test_upload_image_is_converted(self, studio: TestClient, tmp_path: Path) -> None:
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 120, 80))
        pix.clear_with(255)
        png = pix.tobytes("png")
        response = studio.post("/api/upload", files={"file": ("scan.png", png, "image/png")})
        assert response.status_code == 200
        entry = next(
            d
            for d in studio.get("/api/documents").json()["documents"]
            if d["id"] == response.json()["id"]
        )
        assert entry["type"] == "png"

    def test_upload_corrupt_image_rejected_and_cleaned_up(
        self, studio: TestClient, tmp_path: Path
    ) -> None:
        response = studio.post(
            "/api/upload", files={"file": ("broken.png", b"not an image", "image/png")}
        )
        assert response.status_code == 422
        assert not (tmp_path / "broken.png").exists()

    def test_upload_docx_is_converted(self, studio: TestClient, tmp_path: Path) -> None:
        docx = pytest.importorskip("docx")
        import io

        buf = io.BytesIO()
        document = docx.Document()
        document.add_paragraph("Contact email: person@example.com")
        document.save(buf)
        response = studio.post(
            "/api/upload",
            files={
                "file": (
                    "letter.docx",
                    buf.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert response.status_code == 200
        doc_id = response.json()["id"]
        _wait_ready(studio, doc_id)
        plan = studio.get(f"/review/{doc_id}/api/plan").json()
        assert any(e["text"] == "person@example.com" for e in plan["entries"])

    def test_workspace_scan_picks_up_non_pdf_files(self, tmp_path: Path) -> None:
        _make_pdf(tmp_path / "statement.pdf")
        (tmp_path / "notes.txt").write_text("Phone: 9876543210", encoding="utf-8")
        client = TestClient(create_studio_app(tmp_path))
        docs = client.get("/api/documents").json()["documents"]
        names = {d["name"] for d in docs}
        assert names == {"statement.pdf", "notes.txt"}
        # The conversion twin (notes.txt.pdf) must not be listed separately.
        assert (tmp_path / "notes.txt.pdf").exists()

    def test_conversion_twin_not_listed_after_restart(self, tmp_path: Path) -> None:
        (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
        TestClient(create_studio_app(tmp_path))  # first run converts
        client = TestClient(create_studio_app(tmp_path))  # second run re-scans
        docs = client.get("/api/documents").json()["documents"]
        assert [d["name"] for d in docs] == ["notes.txt"]


class TestStudioReviewMount:
    def test_review_page_uses_relative_api_paths(self) -> None:
        """The review page is mounted under /review/{doc_id}/ in studio mode.

        Absolute "/api/..." URLs would resolve against the studio root and
        404 (the page would hang on the loading screen), so every review-page
        request must use a relative "api/..." path.
        """
        from privacy_firewall.ui.html import PAGE_HTML

        assert 'api("/api/' not in PAGE_HTML
        assert '"/api/page/' not in PAGE_HTML
        assert '"/api/preview/' not in PAGE_HTML

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
