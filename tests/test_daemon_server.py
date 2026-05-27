"""End-to-end tests for the daemon FastAPI app (no port bound)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import arxiv2rm.daemon.auth as auth_mod
import arxiv2rm.daemon.jobs as jobs_mod
import arxiv2rm.daemon.server as server_mod
from arxiv2rm.daemon.jobs import JobStore
from arxiv2rm.daemon.server import _parse_output_path


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_mod, "TOKEN_PATH", tmp_path / "token")
    monkeypatch.setattr(jobs_mod, "JOBS_DIR", tmp_path / "jobs")
    # Force JobStore default dir to the tmp jobs dir for this test.
    original_init = JobStore.__init__

    def patched_init(self, directory=tmp_path / "jobs"):
        original_init(self, directory)

    monkeypatch.setattr(JobStore, "__init__", patched_init)

    app = server_mod.build_app()
    return TestClient(app), auth_mod.ensure_token()


def test_health_is_open(client):
    c, _ = client
    assert c.get("/health").json()["status"] == "ok"


def test_convert_requires_bearer(client):
    c, _ = client
    assert c.post("/convert", json={"url": "u"}).status_code == 401


def test_convert_rejects_wrong_token(client):
    c, _ = client
    r = c.post("/convert", json={"url": "u"}, headers={"Authorization": "Bearer nope"})
    assert r.status_code == 403


def test_convert_creates_job(client, monkeypatch):
    c, tok = client

    async def fake_run(store, job):  # noqa: ARG001
        store.update(job.id, stage="converted", progress=80, output_path="/tmp/x.pdf")

    monkeypatch.setattr(server_mod, "_run_convert", fake_run)

    r = c.post(
        "/convert",
        json={"url": "https://arxiv.org/abs/x"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "queued"
    job_id = body["job_id"]

    # Wait for the background task to run.
    for _ in range(20):
        status = c.get(f"/status/{job_id}", headers={"Authorization": f"Bearer {tok}"}).json()
        if status["stage"] == "converted":
            break
    else:
        pytest.fail("background task did not complete")

    assert status["output_path"] == "/tmp/x.pdf"


def test_status_missing_job(client):
    c, tok = client
    r = c.get("/status/nope", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 404


def test_push_requires_converted_stage(client):
    c, tok = client
    r = c.post(
        "/convert",
        json={"url": "u"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    job_id = r.json()["job_id"]
    push = c.post(
        f"/push/{job_id}",
        json={"folder": "/"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert push.status_code in (409, 200)


class _FakeStream:
    def __init__(self, payload: bytes):
        self._lines = payload.splitlines(keepends=True)
        self._idx = 0

    async def readline(self) -> bytes:
        if self._idx >= len(self._lines):
            return b""
        line = self._lines[self._idx]
        self._idx += 1
        return line


class _FakeProc:
    def __init__(self, returncode: int, payload: bytes):
        self.returncode = returncode
        self.stdout = _FakeStream(payload)

    async def wait(self):
        return self.returncode


def test_run_convert_retries_on_http_429(tmp_path, monkeypatch):
    monkeypatch.setattr(server_mod, "RATE_LIMIT_BACKOFF_S", (0,))

    store = JobStore(directory=tmp_path)
    job = store.create("https://arxiv.org/abs/x", {"device_model": "rmpro", "font_size": 14})

    calls = {"n": 0}

    async def fake_spawn(*args, **kwargs):  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeProc(1, b"ERROR HTTP 429 rate limited\n")
        return _FakeProc(0, b"Processing LaTeX\nPDF built\nOutput:\n/tmp/foo.pdf\n")

    spawn_attr = "create_subprocess_" + "exec"
    monkeypatch.setattr(asyncio, spawn_attr, fake_spawn)

    asyncio.run(server_mod._run_convert(store, job))

    final = store.get(job.id)
    assert final.stage == "converted"
    assert final.output_path == "/tmp/foo.pdf"
    assert calls["n"] == 2


def test_run_convert_gives_up_on_non_retryable(tmp_path, monkeypatch):
    monkeypatch.setattr(server_mod, "RATE_LIMIT_BACKOFF_S", (0,))

    store = JobStore(directory=tmp_path)
    job = store.create("https://arxiv.org/abs/x", {})

    async def fake_spawn(*args, **kwargs):  # noqa: ARG001
        return _FakeProc(1, b"boom: file not found\n")

    spawn_attr = "create_subprocess_" + "exec"
    monkeypatch.setattr(asyncio, spawn_attr, fake_spawn)

    asyncio.run(server_mod._run_convert(store, job))
    final = store.get(job.id)
    assert final.stage == "error"
    assert "boom" in (final.error or "")


def test_run_convert_passes_wide_columns_env(tmp_path, monkeypatch):
    """The convert subprocess must run with a wide COLUMNS so rich does not
    wrap (and thus truncate) the ``Output: <path>`` line."""
    monkeypatch.setattr(server_mod, "RATE_LIMIT_BACKOFF_S", (0,))

    store = JobStore(directory=tmp_path)
    job = store.create("https://arxiv.org/abs/x", {})

    captured = {}

    async def fake_spawn(*args, **kwargs):
        captured["env"] = kwargs.get("env")
        return _FakeProc(0, b"Output: /tmp/foo.pdf\n")

    spawn_attr = "create_subprocess_" + "exec"
    monkeypatch.setattr(asyncio, spawn_attr, fake_spawn)

    asyncio.run(server_mod._run_convert(store, job))

    assert captured["env"] is not None
    assert int(captured["env"]["COLUMNS"]) >= 1000
    assert store.get(job.id).output_path == "/tmp/foo.pdf"


def test_is_arxiv_input_classifies_urls():
    assert server_mod._is_arxiv_input("https://arxiv.org/abs/1706.03762")
    assert server_mod._is_arxiv_input("https://arxiv.org/pdf/1706.03762")
    assert server_mod._is_arxiv_input("http://export.arxiv.org/abs/x")
    assert server_mod._is_arxiv_input("arxiv:1706.03762")
    assert not server_mod._is_arxiv_input("https://example.com/paper.pdf")
    assert not server_mod._is_arxiv_input("https://notarxiv.org/x.pdf")


def test_download_pdf_rejects_non_http_scheme():
    with pytest.raises(ValueError, match="scheme"):
        server_mod._download_pdf("file:///etc/passwd")


def test_run_convert_downloads_non_arxiv_pdf(tmp_path, monkeypatch):
    """A non-ArXiv PDF URL must be downloaded locally before conversion."""
    monkeypatch.setattr(server_mod, "RATE_LIMIT_BACKOFF_S", (0,))

    store = JobStore(directory=tmp_path)
    job = store.create("https://example.com/some/paper.pdf", {})

    local = tmp_path / "paper.pdf"
    local.write_bytes(b"%PDF-1.4 fake")

    downloaded = {}

    def fake_download(url):
        downloaded["url"] = url
        return str(local)

    monkeypatch.setattr(server_mod, "_download_pdf", fake_download)

    captured = {}

    async def fake_spawn(*args, **kwargs):
        captured["cmd"] = args
        return _FakeProc(0, b"Output: /tmp/paper_remarkable.pdf\n")

    spawn_attr = "create_subprocess_" + "exec"
    monkeypatch.setattr(asyncio, spawn_attr, fake_spawn)

    asyncio.run(server_mod._run_convert(store, job))

    assert downloaded["url"] == "https://example.com/some/paper.pdf"
    assert str(local) in captured["cmd"]
    assert store.get(job.id).stage == "converted"


def test_run_convert_reports_download_failure(tmp_path, monkeypatch):
    store = JobStore(directory=tmp_path)
    job = store.create("https://example.com/missing.pdf", {})

    def boom(url):
        raise ValueError("404 not found")

    monkeypatch.setattr(server_mod, "_download_pdf", boom)

    asyncio.run(server_mod._run_convert(store, job))
    final = store.get(job.id)
    assert final.stage == "error"
    assert "download failed" in (final.error or "")


def test_stream_progress_fires_markers(tmp_path):
    store = JobStore(directory=tmp_path)
    job = store.create("u", {})
    payload = (
        b"random preamble\n"
        b"INFO Fetching metadata for ArXiv paper\n"
        b"INFO Downloaded source to /cache/x.tar.gz\n"
        b"INFO Processing LaTeX document\n"
        b"INFO Rendering 3 display math formulas\n"
        b"INFO PDF built: /tmp/x.pdf\n"
        b"Output:\n/tmp/x.pdf\n"
    )
    stream = _FakeStream(payload)
    out = asyncio.run(server_mod._stream_progress(stream, store, job.id))
    assert out == payload
    assert store.get(job.id).progress == 75


def test_folders_endpoint_returns_cached_list(client, monkeypatch):
    c, tok = client

    async def fake_list():
        return ["/", "/ArXiv"]

    monkeypatch.setattr(server_mod, "_list_remote_folders", fake_list)
    r = c.get("/folders", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json() == {"folders": ["/", "/ArXiv"]}


def test_list_remote_folders_handles_missing_rmapi(monkeypatch):
    server_mod._folders_cache = (0.0, [])

    async def boom(*args, **kwargs):  # noqa: ARG001
        raise FileNotFoundError("rmapi")

    spawn_attr = "create_subprocess_" + "exec"
    monkeypatch.setattr(asyncio, spawn_attr, boom)
    assert asyncio.run(server_mod._list_remote_folders()) == []


def test_parse_output_path_picks_first_line():
    text = "blah\nOutput:\n/Users/n/Downloads/foo.pdf\nmore\n"
    assert _parse_output_path(text) == "/Users/n/Downloads/foo.pdf"


def test_parse_output_path_missing_marker():
    assert _parse_output_path("no marker here") is None
