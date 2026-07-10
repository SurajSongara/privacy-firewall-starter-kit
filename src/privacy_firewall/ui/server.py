"""FastAPI server for the local review UI.

Requires the ``ui`` extra (``pip install privacy-firewall[ui]``).
The server binds to 127.0.0.1 only — nothing leaves the machine.
"""

from __future__ import annotations

import socket
import threading
import webbrowser
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, Response
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    msg = "The review UI requires the 'ui' extra: pip install privacy-firewall[ui]"
    raise ImportError(msg) from exc

from privacy_firewall.policy.models import Policy
from privacy_firewall.ui.html import PAGE_HTML
from privacy_firewall.ui.session import ReviewSession


class DecisionRequest(BaseModel):
    """A decision toggle from the UI."""

    detection_id: str
    decision: str | None = None


class ApplyRequest(BaseModel):
    """Apply request; output path is optional."""

    output_path: str | None = None


def create_app(session: ReviewSession) -> FastAPI:
    """Build the review app around one ReviewSession.

    Args:
        session: The session holding the document, plan, and page images.

    Returns:
        The configured FastAPI application.
    """
    app = FastAPI(title="Privacy Firewall Review", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return PAGE_HTML

    @app.get("/api/plan")
    def plan() -> dict:  # type: ignore[type-arg]
        return session.summary()

    @app.get("/api/page/{page_number}")
    def page_png(page_number: int) -> Response:
        try:
            png = session.page_png(page_number)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(content=png, media_type="image/png")

    @app.post("/api/decision")
    def decision(request: DecisionRequest) -> dict:  # type: ignore[type-arg]
        if request.decision not in (None, "redact", "keep"):
            raise HTTPException(status_code=422, detail="decision must be redact/keep/null")
        if not session.set_decision(request.detection_id, request.decision):
            raise HTTPException(status_code=404, detail="unknown detection_id")
        return {"ok": True, "counts": session.plan.counts()}

    @app.post("/api/apply")
    def apply(request: ApplyRequest) -> dict:  # type: ignore[type-arg]
        output = Path(request.output_path) if request.output_path else None
        out_path, count = session.apply(output)
        return {
            "output_path": str(out_path),
            "redactions": count,
            "plan_path": str(session.plan_file_path),
        }

    @app.post("/api/save")
    def save() -> dict:  # type: ignore[type-arg]
        return {"plan_path": str(session.save_plan())}

    return app


def _free_port() -> int:
    """Ask the OS for an available localhost port."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_review(
    pdf_path: Path,
    policy: Policy,
    *,
    port: int | None = None,
    open_browser: bool = True,
    force_ocr: bool = False,
    auto: bool = False,
    ocr_provider: str | None = None,
) -> None:
    """Run the pipeline, then serve the review UI (blocks until Ctrl+C).

    Args:
        pdf_path: The PDF to review.
        policy: Policy for the suggested actions.
        port: Fixed port, or ``None`` for an OS-assigned free port.
        open_browser: Open the default browser once the server starts.
        force_ocr: Force the OCR pipeline.
        auto: Let diagnostics choose the pipeline.
        ocr_provider: Specific OCR engine name.
    """
    import uvicorn

    session = ReviewSession(
        pdf_path, policy, force_ocr=force_ocr, auto=auto, ocr_provider=ocr_provider
    )
    app = create_app(session)

    chosen_port = port if port is not None else _free_port()
    url = f"http://127.0.0.1:{chosen_port}"
    print(f"Review UI: {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()

    uvicorn.run(app, host="127.0.0.1", port=chosen_port, log_level="warning")
