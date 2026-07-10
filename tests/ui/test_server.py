"""Tests for the review UI server (requires the ui extra + httpx)."""

from pathlib import Path

import fitz
import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from privacy_firewall.policy import BUILTIN_POLICIES  # noqa: E402
from privacy_firewall.ui.server import create_app  # noqa: E402
from privacy_firewall.ui.session import ReviewSession  # noqa: E402


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    path = tmp_path / "doc.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "PAN: AAAAA1111A", fontsize=12)
    page.insert_text((50, 140), "Email: user@example.com", fontsize=12)
    doc.save(str(path))
    doc.close()
    session = ReviewSession(path, BUILTIN_POLICIES["share-with-ai"])
    return TestClient(create_app(session))


class TestReviewServer:
    def test_index_serves_html(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "Privacy Firewall" in response.text

    def test_plan_endpoint(self, client: TestClient) -> None:
        plan = client.get("/api/plan").json()
        assert plan["policy"] == "share-with-ai"
        assert len(plan["entries"]) >= 2
        assert plan["pages"][0]["width"] > 0

    def test_page_png(self, client: TestClient) -> None:
        response = client.get("/api/page/1")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content[:8] == b"\x89PNG\r\n\x1a\n"

    def test_page_out_of_range_404(self, client: TestClient) -> None:
        assert client.get("/api/page/99").status_code == 404

    def test_decision_round_trip(self, client: TestClient) -> None:
        entry = client.get("/api/plan").json()["entries"][0]
        response = client.post(
            "/api/decision",
            json={"detection_id": entry["detection_id"], "decision": "keep"},
        )
        assert response.status_code == 200
        updated = client.get("/api/plan").json()["entries"][0]
        assert updated["decision"] == "keep"

    def test_decision_unknown_id_404(self, client: TestClient) -> None:
        response = client.post(
            "/api/decision", json={"detection_id": "nope", "decision": "keep"}
        )
        assert response.status_code == 404

    def test_decision_invalid_value_422(self, client: TestClient) -> None:
        entry = client.get("/api/plan").json()["entries"][0]
        response = client.post(
            "/api/decision",
            json={"detection_id": entry["detection_id"], "decision": "maybe"},
        )
        assert response.status_code == 422

    def test_apply(self, client: TestClient, tmp_path: Path) -> None:
        out = tmp_path / "redacted.pdf"
        response = client.post("/api/apply", json={"output_path": str(out)})
        assert response.status_code == 200
        body = response.json()
        assert body["redactions"] >= 1
        assert Path(body["output_path"]).exists()
        assert Path(body["plan_path"]).exists()
