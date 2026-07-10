"""Studio mode: a local web dashboard for browsing and opening PDFs to review.

Requires the ``ui`` extra (``pip install privacy-firewall[ui]``).
The server binds to 127.0.0.1 only — nothing leaves the machine.

The dashboard (``/``) lists the PDFs in a workspace folder and accepts
uploads; opening a document mounts the existing single-session review app
(``create_app`` from :mod:`privacy_firewall.ui.server`) under
``/review/{doc_id}/`` so the rest of the review flow is reused unchanged.
"""

from __future__ import annotations

import re
import socket
import threading
from pathlib import Path
from typing import Any

from privacy_firewall.policy import DEFAULT_POLICY_NAME, get_policy

try:
    from fastapi import FastAPI, File, HTTPException, UploadFile
    from fastapi.responses import HTMLResponse
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    msg = "The studio UI requires the 'ui' extra: pip install privacy-firewall[ui]"
    raise ImportError(msg) from exc

from privacy_firewall.ui.html import STUDIO_HTML
from privacy_firewall.ui.server import create_app
from privacy_firewall.ui.session import ReviewSession


def _slugify(name: str) -> str:
    """Turn a filename into a safe URL path segment for a doc id."""
    stem = Path(name).stem
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()
    return slug or "doc"


def _secure_filename(name: str) -> str:
    """Sanitise an upload filename, keeping its extension (no path traversal)."""
    name = Path(name).name
    stem, ext = Path(name).stem, Path(name).suffix
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", stem)
    safe = safe or "document"
    return safe + (ext or ".pdf")


def _unique_name(workspace: Path, name: str) -> str:
    """Return a non-conflicting filename next to *name* in *workspace*."""
    base = Path(name)
    stem, ext = base.stem, base.suffix
    i = 2
    while (workspace / f"{stem}-{i}{ext}").exists():
        i += 1
    return f"{stem}-{i}{ext}"


def _iter_pdfs(workspace: Path) -> list[Path]:
    """Top-level PDFs in *workspace*, excluding already-redacted outputs."""
    return [
        p
        for p in sorted(workspace.glob("*.pdf"))
        if not p.name.endswith(".redacted.pdf")
    ]


def create_studio_app(
    workspace: Path, policy_name: str = DEFAULT_POLICY_NAME
) -> FastAPI:
    """Build the studio dashboard app around the PDFs in *workspace*.

    Every PDF in the workspace (and any uploaded later) gets a review
    sub-application mounted at ``/review/{doc_id}/``; the pipeline for each
    runs in the background so the review page is ready by the time it opens.

    Args:
        workspace: Folder scanned for PDFs and used to store uploads.
        policy_name: Policy name for the suggested actions in each review.

    Returns:
        The configured FastAPI studio application.
    """
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    policy = get_policy(policy_name)

    app = FastAPI(title="Privacy Firewall Studio", docs_url=None, redoc_url=None)
    sessions: dict[str, ReviewSession] = {}
    lock = threading.Lock()

    def ensure_mounted(pdf_path: Path) -> str:
        """Mount (or reuse) a review sub-app for *pdf_path*; return its doc id."""
        pdf_path = Path(pdf_path).resolve()
        base = _slugify(pdf_path.name)
        with lock:
            for doc_id, session in sessions.items():
                if Path(session.pdf_path).resolve() == pdf_path:
                    return doc_id
            doc_id = base
            n = 2
            while doc_id in sessions:
                doc_id = f"{base}-{n}"
                n += 1

            session = ReviewSession(pdf_path, policy, lazy=True)
            sub = create_app(session)

            def worker() -> None:
                try:
                    session.run()
                except Exception:  # noqa: BLE001 - surfaced via /api/status
                    pass

            threading.Thread(target=worker, daemon=True).start()
            app.mount(f"/review/{doc_id}", sub)
            sessions[doc_id] = session
        return doc_id

    # Warm up: mount every PDF already present in the workspace.
    for pdf in _iter_pdfs(workspace):
        try:
            ensure_mounted(pdf)
        except Exception:  # noqa: BLE001 - a broken PDF shouldn't kill the studio
            pass

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return STUDIO_HTML

    @app.get("/api/documents")
    def documents() -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for doc_id in sorted(sessions, key=lambda d: sessions[d].pdf_path.name):
            session = sessions[doc_id]
            pdf = Path(session.pdf_path)
            if not pdf.exists():
                continue
            stat = pdf.stat()
            items.append(
                {
                    "id": doc_id,
                    "name": pdf.name,
                    "size": stat.st_size,
                    "modified": int(stat.st_mtime),
                    "has_plan": pdf.with_suffix(".review.json").exists(),
                }
            )
        return {"documents": items}

    @app.post("/api/upload")
    async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=422, detail="Only .pdf files are accepted")
        dest = workspace / _secure_filename(file.filename)
        if dest.exists():
            dest = workspace / _unique_name(workspace, dest.name)
        data = await file.read()
        if not data.startswith(b"%PDF"):
            raise HTTPException(status_code=422, detail="File does not look like a PDF")
        dest.write_bytes(data)
        doc_id = ensure_mounted(dest)
        return {"id": doc_id, "name": dest.name}

    return app


def _free_port() -> int:
    """Ask the OS for an available localhost port."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_studio(
    workspace: Path,
    *,
    port: int | None = None,
    open_browser: bool = True,
    policy_name: str = DEFAULT_POLICY_NAME,
) -> None:
    """Serve the studio dashboard; blocks until Ctrl+C.

    Args:
        workspace: Folder scanned for PDFs and used to store uploads.
        port: Fixed port, or ``None`` for an OS-assigned free port.
        open_browser: Open the default browser once the server starts.
        policy_name: Policy name used for the suggested actions in reviews.
    """
    import webbrowser

    app = create_studio_app(workspace, policy_name=policy_name)

    chosen_port = port if port is not None else _free_port()
    url = f"http://127.0.0.1:{chosen_port}"
    print(f"Privacy Firewall Studio: {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=chosen_port, log_level="warning")
