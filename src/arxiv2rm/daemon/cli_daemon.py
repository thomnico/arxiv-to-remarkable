"""CLI entry point for the local daemon: ``arxiv2rm-daemon``.

Subcommands:

* ``arxiv2rm-daemon start``   — start uvicorn in the foreground.
* ``arxiv2rm-daemon status``  — probe ``/health`` against the running daemon.
* ``arxiv2rm-daemon stop``    — send SIGTERM to the PID recorded on start.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

import click

from arxiv2rm.daemon.auth import TOKEN_PATH, ensure_token

PID_PATH = Path.home() / ".arxiv2rm" / "daemon.pid"


def _read_pid() -> int | None:
    if not PID_PATH.exists():
        return None
    try:
        return int(PID_PATH.read_text().strip())
    except ValueError:
        return None


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@click.group()
def main() -> None:
    """arxiv2rm local HTTP daemon."""


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=7842, show_default=True, type=int)
@click.option("--log-level", default="info", show_default=True)
def start(host: str, port: int, log_level: str) -> None:
    """Start the daemon in the foreground."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("uvicorn missing. Install with: pip install -e '.[daemon]'") from exc

    from arxiv2rm.daemon.server import build_app

    existing = _read_pid()
    if existing and _process_alive(existing):
        click.echo(f"Daemon already running (pid {existing}).", err=True)
        sys.exit(1)

    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()))

    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))
    token = ensure_token()
    click.echo(f"Daemon token ({TOKEN_PATH}): {token}")
    click.echo(f"Listening on http://{host}:{port}")
    try:
        uvicorn.run(build_app(), host=host, port=port, log_level=log_level)
    finally:
        try:
            PID_PATH.unlink()
        except FileNotFoundError:
            pass


@main.command()
@click.option("--port", default=7842, show_default=True, type=int)
def status(port: int) -> None:
    """Probe ``/health`` and report whether the daemon is responsive."""
    import urllib.error
    import urllib.request

    pid = _read_pid()
    if pid:
        click.echo(f"PID file: {pid} ({'alive' if _process_alive(pid) else 'stale'})")
    else:
        click.echo("PID file: (none)")

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health", timeout=2
        ) as resp:
            click.echo(f"HTTP {resp.status}: {resp.read().decode()}")
    except (urllib.error.URLError, ConnectionError) as exc:
        click.echo(f"unreachable: {exc}", err=True)
        sys.exit(2)


@main.command()
def stop() -> None:
    """Send SIGTERM to the running daemon (if any)."""
    pid = _read_pid()
    if not pid:
        click.echo("No PID file; daemon not running.", err=True)
        sys.exit(1)
    if not _process_alive(pid):
        click.echo("PID file points to dead process; cleaning up.")
        PID_PATH.unlink(missing_ok=True)
        return
    os.kill(pid, signal.SIGTERM)
    click.echo(f"SIGTERM sent to pid {pid}")


if __name__ == "__main__":
    main()
