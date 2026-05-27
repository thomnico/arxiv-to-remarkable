"""Local HTTP daemon exposing arxiv2rm to the Chrome extension.

``build_app`` is imported lazily so that the rest of the package keeps working
even when the optional ``[daemon]`` extra (fastapi + uvicorn) is not installed.
"""

from __future__ import annotations


def build_app():  # pragma: no cover - thin shim
    from arxiv2rm.daemon.server import build_app as _build

    return _build()


__all__ = ["build_app"]
