"""FastAPI app exposing /convert, /status, /push to the Chrome extension.

Binds 127.0.0.1 only. Auth via Authorization: Bearer header. CORS limited to
chrome-extension origins. Subprocesses use argv lists (no shell).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import shutil
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

try:
    from fastapi import Depends, FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Daemon requires fastapi + uvicorn. Install with: pip install -e '.[daemon]'"
    ) from exc

from arxiv2rm.daemon.auth import ensure_token
from arxiv2rm.daemon.jobs import Job, JobStore

logger = logging.getLogger(__name__)


class ConvertRequest(BaseModel):
    url: str
    font_size: int = 14
    device_model: str = "rmpro"
    columns: bool = True


class PushRequest(BaseModel):
    folder: str = "/"


def _check_auth(request: Request, token: str) -> None:
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    presented = header.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(presented, token):
        raise HTTPException(status_code=403, detail="Invalid token")


def build_app() -> FastAPI:
    token = ensure_token()
    store = JobStore()
    app = FastAPI(title="arxiv2rm daemon", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"chrome-extension://.*",
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    def auth(request: Request) -> None:
        _check_auth(request, token)

    @app.get("/health")
    def health():
        return {"status": "ok", "version": app.version}

    @app.post("/convert")
    async def convert(req: ConvertRequest, _: None = Depends(auth)):
        job = store.create(req.url, req.model_dump())
        asyncio.create_task(_run_convert(store, job))
        return {"job_id": job.id, "stage": job.stage}

    @app.get("/status/{job_id}")
    def status(job_id: str, _: None = Depends(auth)):
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    @app.get("/folders")
    async def folders(_: None = Depends(auth)):
        return {"folders": await _list_remote_folders()}

    @app.post("/push/{job_id}")
    async def push(job_id: str, req: PushRequest, _: None = Depends(auth)):
        job = store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        if job.stage not in ("converted", "done"):
            raise HTTPException(status_code=409, detail=f"job stage is {job.stage}")
        asyncio.create_task(_run_push(store, job, req.folder))
        return {"job_id": job.id, "stage": "pushing"}

    return app


RATE_LIMIT_BACKOFF_S = (30, 60, 120)

# Heuristic markers in arxiv2rm stdout → progress percentage. Each rule fires
# the first time the substring appears; the daemon stays at the last seen value
# otherwise. Kept conservative (max 75) so the final "converted" stage can still
# bump to 80.
PROGRESS_MARKERS: list[tuple[str, int]] = [
    ("Fetching metadata", 25),
    ("Downloaded source", 35),
    ("Processing LaTeX", 45),
    ("Rendering", 60),
    ("PDF built", 75),
]


async def _stream_progress(reader: asyncio.StreamReader, store: JobStore, job_id: str) -> bytes:
    """Drain ``reader`` line by line, updating job progress as markers appear."""
    fired: set[str] = set()
    chunks: list[bytes] = []
    while True:
        line = await reader.readline()
        if not line:
            break
        chunks.append(line)
        decoded = line.decode("utf-8", errors="replace")
        for marker, pct in PROGRESS_MARKERS:
            if marker in fired or marker not in decoded:
                continue
            fired.add(marker)
            store.update(job_id, progress=pct)
            break
    return b"".join(chunks)


_ARXIV_URL_RE = re.compile(r"^https?://(?:[\w-]+\.)?arxiv\.org/", re.IGNORECASE)

DOWNLOADS_DIR = Path.home() / ".arxiv2rm" / "cache" / "downloads"


def _is_arxiv_input(url: str) -> bool:
    """True when ``arxiv2rm convert`` can consume the URL directly."""
    return bool(_ARXIV_URL_RE.match(url)) or url.lower().startswith(("arxiv:", "arxiv :"))


def _download_pdf(url: str) -> str:
    """Fetch a non-ArXiv PDF to the local cache and return its path.

    ``arxiv2rm convert`` routes every URL through the ArXiv client, so plain
    PDF links (the extension's right-click flow) must be downloaded first and
    converted as local files. Raises on network errors or non-PDF content.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"unsupported URL scheme: {parsed.scheme or '(none)'}")
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    name = Path(parsed.path).name or "download"
    name = re.sub(r"[^\w.-]", "_", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    dest = DOWNLOADS_DIR / name
    req = urllib.request.Request(url, headers={"User-Agent": "arxiv2rm-daemon/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (http(s) only)
        head = resp.read(5)
        if not head.startswith(b"%PDF"):
            raise ValueError("URL did not return a PDF document")
        with open(dest, "wb") as fh:
            fh.write(head)
            shutil.copyfileobj(resp, fh)
    return str(dest)


async def _run_convert(store: JobStore, job: Job) -> None:
    store.update(job.id, stage="downloading", progress=10)

    convert_input = job.url
    if not _is_arxiv_input(job.url):
        try:
            convert_input = await asyncio.to_thread(_download_pdf, job.url)
        except Exception as exc:  # noqa: BLE001
            logger.exception("PDF download failed")
            store.update(job.id, stage="error", error=f"PDF download failed: {exc}")
            return

    cmd = [
        "arxiv2rm",
        "convert",
        convert_input,
        "--device",
        job.options.get("device_model", "rmpro"),
        "--font-size",
        str(job.options.get("font_size", 14)),
    ]
    if not job.options.get("columns", True):
        cmd.append("--no-columns")

    # arxiv2rm prints "Output: <path>" via a rich Console, which wraps long
    # lines at 80 cols when stdout is a pipe — truncating the parsed path. A
    # wide COLUMNS keeps the path on a single line so _parse_output_path works.
    env = os.environ.copy()
    env["COLUMNS"] = "1000"

    text = ""
    try:
        for attempt, wait in enumerate((0,) + RATE_LIMIT_BACKOFF_S):
            if wait:
                await asyncio.sleep(wait)
            store.update(
                job.id,
                stage="converting",
                progress=20 + attempt * 5,
            )
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
            out = await _stream_progress(proc.stdout, store, job.id)
            await proc.wait()
            text = out.decode("utf-8", errors="replace")
            if proc.returncode == 0:
                output_path = _parse_output_path(text)
                store.update(job.id, stage="converted", progress=80, output_path=output_path)
                return
            if "HTTP 429" not in text:
                break  # non-retryable
        store.update(job.id, stage="error", error=text[-2000:] or "convert failed")
    except Exception as exc:  # noqa: BLE001
        logger.exception("convert failed")
        store.update(job.id, stage="error", error=str(exc))


async def _run_push(store: JobStore, job: Job, folder: str) -> None:
    if not job.output_path or not Path(job.output_path).exists():
        store.update(job.id, stage="error", error="output PDF missing on disk")
        return
    store.update(job.id, stage="pushing", progress=90)
    # Upload via rm_cloud (inkan_doc) directly against the reMarkable Cloud API,
    # avoiding the rmapi CLI which broke on schema 4. Folder placement is not
    # yet supported by rm_cloud.upload_document (destination is ignored); the
    # document lands at root and `remote_path` records the resulting doc id.
    from arxiv2rm import rm_cloud

    try:
        result = await asyncio.to_thread(
            rm_cloud.upload_document, job.output_path, folder if folder != "/" else None
        )
    except FileNotFoundError as exc:
        store.update(job.id, stage="error", error=str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("push failed")
        store.update(job.id, stage="error", error=str(exc))
        return

    doc_id = result.get("id", "")
    name = Path(job.output_path).stem
    remote = f"{folder.rstrip('/')}/{name} [{doc_id}]" if doc_id else folder
    store.update(job.id, stage="done", progress=100, remote_path=remote)


_folders_cache: tuple[float, list[str]] = (0.0, [])
_FOLDERS_TTL_S = 60.0


async def _list_remote_folders() -> list[str]:
    """Return the list of remote directories built from rm_cloud's listing.

    Cached for 60 seconds. Empty list on any failure so the popup can fall back
    to a free-text input.
    """
    import time

    global _folders_cache
    now = time.time()
    if now - _folders_cache[0] < _FOLDERS_TTL_S and _folders_cache[1]:
        return _folders_cache[1]
    try:
        from arxiv2rm import rm_cloud

        docs = await asyncio.to_thread(rm_cloud.list_documents)
    except Exception:  # noqa: BLE001
        logger.exception("folder listing failed")
        return []

    # Resolve full paths by walking parent ids. Folders are CollectionType.
    by_id = {d.id: d for d in docs}
    folders: list[str] = []
    for d in docs:
        if d.type != "CollectionType":
            continue
        parts: list[str] = [d.name]
        cur = d.parent
        seen: set[str] = {d.id}
        while cur and cur in by_id and cur not in seen:
            seen.add(cur)
            parent = by_id[cur]
            parts.append(parent.name)
            cur = parent.parent
        folders.append("/" + "/".join(reversed(parts)))

    folders = sorted(set(folders)) or ["/"]
    _folders_cache = (now, folders)
    return folders


def _parse_output_path(text: str) -> Optional[str]:
    marker = "Output:"
    if marker not in text:
        return None
    tail = text.split(marker, 1)[1].strip()
    return tail.splitlines()[0].strip() if tail else None
