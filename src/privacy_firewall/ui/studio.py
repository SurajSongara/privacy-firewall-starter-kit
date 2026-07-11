"""Studio mode: a local web dashboard for browsing and opening documents.

Requires the ``ui`` extra (``pip install privacy-firewall[ui]``).
The server binds to 127.0.0.1 only — nothing leaves the machine.

The dashboard (``/``) lists the supported documents in a workspace folder
(PDF, images, txt, md, docx) and accepts uploads; non-PDF formats are
converted to PDF once (``<name>.pdf`` next to the source) and the existing
single-session review app (``create_app`` from
:mod:`privacy_firewall.ui.server`) is mounted under ``/review/{doc_id}/``
so the rest of the review flow is reused unchanged.
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

from privacy_firewall.parsers.converters import (
    SUPPORTED_SUFFIXES,
    ConversionError,
    convert_to_pdf,
    needs_conversion,
)
from privacy_firewall.ui.html import STUDIO_HTML
from privacy_firewall.ui.server import create_app
from privacy_firewall.ui.session import ReviewSession
from privacy_firewall.ui.terms import TermsStore


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
    return safe + ext.lower()


def _unique_name(workspace: Path, name: str) -> str:
    """Return a non-conflicting filename next to *name* in *workspace*."""
    base = Path(name)
    stem, ext = base.stem, base.suffix
    i = 2
    while (workspace / f"{stem}-{i}{ext}").exists():
        i += 1
    return f"{stem}-{i}{ext}"


def _iter_documents(workspace: Path) -> list[Path]:
    """Top-level supported documents in *workspace*.

    Excludes redacted outputs and the ``<source>.pdf`` twins produced by
    converting non-PDF sources (the source file itself is listed instead).
    """
    docs: list[Path] = []
    for p in sorted(workspace.iterdir()):
        if not p.is_file() or p.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if p.name.endswith(".redacted.pdf"):
            continue
        # "photo.png.pdf" is the conversion twin of "photo.png" — skip it.
        if p.suffix.lower() == ".pdf" and needs_conversion(p.stem) and p.with_suffix("").exists():
            continue
        docs.append(p)
    return docs


def create_studio_app(workspace: Path, policy_name: str = DEFAULT_POLICY_NAME) -> FastAPI:
    """Build the studio dashboard app around the documents in *workspace*.

    Every supported document in the workspace (and any uploaded later) gets
    a review sub-application mounted at ``/review/{doc_id}/``; non-PDF
    sources are converted to ``<name>.pdf`` first, and each pipeline runs
    in the background so the review page is ready by the time it opens.

    Args:
        workspace: Folder scanned for documents and used to store uploads.
        policy_name: Policy name for the suggested actions in each review.

    Returns:
        The configured FastAPI studio application.
    """
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    policy = get_policy(policy_name)
    terms_store = TermsStore.for_workspace(workspace)

    app = FastAPI(title="Privacy Firewall Studio", docs_url=None, redoc_url=None)
    sessions: dict[str, ReviewSession] = {}
    sources: dict[str, Path] = {}
    lock = threading.Lock()

    def ensure_mounted(source_path: Path) -> str:
        """Mount (or reuse) a review sub-app for *source_path*; return its doc id.

        Non-PDF sources are converted to ``<name>.pdf`` beside the source
        (cached by modification time); the review session runs on the PDF.

        Raises:
            ConversionError: If a non-PDF source cannot be converted.
        """
        source_path = Path(source_path).resolve()
        if needs_conversion(source_path):
            pdf_path = convert_to_pdf(source_path, source_path.with_name(source_path.name + ".pdf"))
        else:
            pdf_path = source_path
        base = _slugify(source_path.name)
        with lock:
            for doc_id, existing in sources.items():
                if existing == source_path:
                    return doc_id
            doc_id = base
            n = 2
            while doc_id in sessions:
                doc_id = f"{base}-{n}"
                n += 1

            # auto=True lets diagnostics route image-only documents
            # (scans, converted photos) through OCR.
            session = ReviewSession(pdf_path, policy, lazy=True, auto=True, terms_store=terms_store)
            sub = create_app(session)

            def worker() -> None:
                try:
                    session.run()
                except Exception:  # noqa: BLE001 - surfaced via /api/status
                    pass

            threading.Thread(target=worker, daemon=True).start()
            app.mount(f"/review/{doc_id}", sub)
            sessions[doc_id] = session
            sources[doc_id] = source_path
        return doc_id

    # Warm up: mount every supported document already in the workspace.
    for doc in _iter_documents(workspace):
        try:
            ensure_mounted(doc)
        except Exception:  # noqa: BLE001 - a broken file shouldn't kill the studio
            pass

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return STUDIO_HTML

    @app.get("/api/documents")
    def documents() -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for doc_id in sorted(sources, key=lambda d: sources[d].name):
            source = sources[doc_id]
            if not source.exists():
                continue
            stat = source.stat()
            items.append(
                {
                    "id": doc_id,
                    "name": source.name,
                    "type": source.suffix.lstrip(".").lower() or "file",
                    "size": stat.st_size,
                    "modified": int(stat.st_mtime),
                    "has_plan": sessions[doc_id].plan_file_path.exists(),
                }
            )
        return {"documents": items, "terms": len(terms_store.active_terms())}

    @app.post("/api/upload")
    async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
        suffix = Path(file.filename or "").suffix.lower()
        if not file.filename or suffix not in SUPPORTED_SUFFIXES:
            accepted = ", ".join(sorted(SUPPORTED_SUFFIXES))
            raise HTTPException(
                status_code=422, detail=f"Unsupported file type; accepted: {accepted}"
            )
        dest = workspace / _secure_filename(file.filename)
        if dest.exists():
            dest = workspace / _unique_name(workspace, dest.name)
        data = await file.read()
        if suffix == ".pdf" and not data.startswith(b"%PDF"):
            raise HTTPException(status_code=422, detail="File does not look like a PDF")
        dest.write_bytes(data)
        try:
            doc_id = ensure_mounted(dest)
        except ConversionError as exc:
            dest.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
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
        workspace: Folder scanned for documents and used to store uploads.
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
