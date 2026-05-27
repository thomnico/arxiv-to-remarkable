"""Tests for arxiv2rm-daemon CLI (status/stop helpers; no port bound)."""

import os

from click.testing import CliRunner

import arxiv2rm.daemon.cli_daemon as cli_mod


def test_status_no_pid_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_mod, "PID_PATH", tmp_path / "daemon.pid")
    runner = CliRunner()
    result = runner.invoke(cli_mod.main, ["status", "--port", "59999"])
    assert "(none)" in result.output
    assert result.exit_code == 2  # unreachable


def test_stop_without_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_mod, "PID_PATH", tmp_path / "daemon.pid")
    runner = CliRunner()
    result = runner.invoke(cli_mod.main, ["stop"])
    assert result.exit_code == 1
    assert "not running" in result.output


def test_stop_stale_pid(tmp_path, monkeypatch):
    pid_path = tmp_path / "daemon.pid"
    pid_path.write_text("999999")  # very unlikely to exist
    monkeypatch.setattr(cli_mod, "PID_PATH", pid_path)
    runner = CliRunner()
    result = runner.invoke(cli_mod.main, ["stop"])
    assert result.exit_code == 0
    assert "dead process" in result.output
    assert not pid_path.exists()


def test_stop_signals_live_pid(tmp_path, monkeypatch):
    pid_path = tmp_path / "daemon.pid"
    pid_path.write_text(str(os.getpid()))  # current process is alive
    monkeypatch.setattr(cli_mod, "PID_PATH", pid_path)

    sent = {}

    def fake_kill(pid, sig):
        sent["pid"] = pid
        sent["sig"] = sig

    monkeypatch.setattr(cli_mod.os, "kill", fake_kill)
    monkeypatch.setattr(cli_mod, "_process_alive", lambda pid: True)

    runner = CliRunner()
    result = runner.invoke(cli_mod.main, ["stop"])
    assert result.exit_code == 0
    assert sent["pid"] == os.getpid()
