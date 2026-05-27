"""Tests for arxiv2rm.daemon.auth."""

from pathlib import Path

import arxiv2rm.daemon.auth as auth_mod


def test_ensure_token_generates_then_reads(tmp_path, monkeypatch):
    token_path = tmp_path / "daemon.token"
    monkeypatch.setattr(auth_mod, "TOKEN_PATH", token_path)

    first = auth_mod.ensure_token()
    assert len(first) == 64  # 32 bytes hex
    assert token_path.read_text().strip() == first

    second = auth_mod.ensure_token()
    assert first == second


def test_ensure_token_writes_user_only_permissions(tmp_path, monkeypatch):
    token_path = tmp_path / "daemon.token"
    monkeypatch.setattr(auth_mod, "TOKEN_PATH", token_path)
    auth_mod.ensure_token()

    mode = token_path.stat().st_mode & 0o777
    assert mode == 0o600
