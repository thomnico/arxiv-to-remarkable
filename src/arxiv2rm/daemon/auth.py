"""Bearer-token auth for the local daemon.

The token lives in ``~/.arxiv2rm/daemon.token`` (mode 0600). It is generated on
first startup; the user copies it into the Chrome extension options page.
"""

from __future__ import annotations

import secrets
from pathlib import Path

TOKEN_PATH = Path.home() / ".arxiv2rm" / "daemon.token"


def ensure_token() -> str:
    """Return the daemon token, creating it if missing."""
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text().strip()
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(32)
    TOKEN_PATH.write_text(token)
    TOKEN_PATH.chmod(0o600)
    return token
