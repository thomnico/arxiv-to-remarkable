# TASKS — Chrome Extension: ArXiv → reMarkable

Companion to [PRD-chrome-extension.md](./PRD-chrome-extension.md). Each task ships
independently. Tick as completed.

Legend: ✅ done · 🟡 in progress · ⬜ todo · 🧊 deferred

---

## M0 — Scaffold ✅ (2026-05-22)

- ✅ `src/arxiv2rm/daemon/__init__.py` (lazy `build_app`)
- ✅ `src/arxiv2rm/daemon/auth.py` — bearer token at `~/.arxiv2rm/daemon.token`
- ✅ `src/arxiv2rm/daemon/jobs.py` — in-memory store + JSON spill
- ✅ `src/arxiv2rm/daemon/server.py` — FastAPI app, `/health /convert /status /push`
- ✅ `src/arxiv2rm/daemon/cli_daemon.py` — `arxiv2rm-daemon` entry point
- ✅ `chrome-extension/manifest.json` (MV3, action + content script + context menu)
- ✅ `chrome-extension/background.js` — service worker, polling, notifications
- ✅ `chrome-extension/content.js` — ArXiv page detection (placeholder)
- ✅ `chrome-extension/popup.{html,js,css}` — per-tab UI
- ✅ `chrome-extension/options.{html,js}` — settings
- ✅ `chrome-extension/icons/{16,48,128}.png` — placeholders
- ✅ `chrome-extension/README.md`
- ✅ `pyproject.toml` — `daemon` extra + `arxiv2rm-daemon` script

## M1 — End-to-end wiring 🟡

Goal: from a fresh checkout, one ArXiv URL reaches reMarkable.

- ✅ `pip install -e '.[daemon]'` succeeds on macOS Python 3.14.
- ✅ Daemon endpoints validated in-process via FastAPI `TestClient` (health/auth/convert/status/push).
- ✅ Real `arxiv2rm-daemon start` smoke (2026-05-22): live daemon on `:7842`,
  `/health` + auth (401/403/404), `/convert` of `arxiv.org/abs/1706.03762`
  → `converted` with valid PDF, `/convert` of a non-ArXiv PDF URL → `converted`.
  Two bugs found and fixed:
  - **Truncated `output_path`** (`…remarkable.p`): rich wrapped the `Output:`
    line at 80 cols. Daemon now runs the convert subprocess with `COLUMNS=1000`.
  - **Non-ArXiv PDF URLs rejected** (`arxiv2rm convert` routes every URL to the
    ArXiv client). Daemon now downloads non-ArXiv PDFs locally first
    (`~/.arxiv2rm/cache/downloads/`) and converts the file.
- 🟡 Real `/push` smoke (2026-05-22): daemon ran `rmapi put`, captured the
  failure, set `stage=error` — error path verified. Happy path **blocked** by
  the local rmapi environment: the reMarkable cloud now expects schema 3 but
  rmapi has a stale schema-4 `rootIndex` cached and is rate-limited (HTTP 429).
  Daemon no longer forces `RMAPI_FORCE_SCHEMA_VERSION=4`. Needs rmapi re-sync.
- ⬜ Extension loads unpacked in Chrome without manifest warnings (manifest +
  JS syntax + HTML/JS element IDs validated statically; in-browser load pending
  — requires the OS file picker, not automatable).
- ⬜ Options page round-trips daemon URL + token (`chrome.storage.sync`).
- ⬜ Health dot turns green on ArXiv abs page.
- ⬜ Send → job completes → notification with remote path.
- ⬜ Document the first-run flow in `chrome-extension/README.md` with screenshots.
- ⬜ Capture one failure mode (daemon down) and verify popup error path.

## M2 — Robustness 🟡

- ✅ Replace `==` token check with `secrets.compare_digest`.
- ✅ `arxiv2rm-daemon` is now a click group with `start | status | stop` and PID file at `~/.arxiv2rm/daemon.pid`.
- ✅ Convert subprocess: stream stdout line by line; markers (`Fetching metadata`, `Downloaded source`, `Processing LaTeX`, `Rendering`, `PDF built`) bump progress 25 → 75.
- ✅ Retry ArXiv 429s with backoff (30s, 60s, 120s).
- ✅ Reload persisted jobs from `~/.arxiv2rm/jobs/` on startup (in-flight → `error` with `[daemon restart]` suffix).
- ✅ Unit tests: `tests/test_daemon_jobs.py`, `tests/test_daemon_auth.py`.
- ✅ Server tests via `TestClient`: `tests/test_daemon_server.py` (auth, retry, parse). CLI tests: `tests/test_daemon_cli.py` (status/stop branches).

## M3 — Badge + content script 🟡

- ✅ `content.js` sends `{type:"page-detected", url, title}` to background.
- ✅ Background caches per-tab detection and sets a green `●` badge on ArXiv match.
- ✅ Reset badge on tab navigation (`chrome.tabs.onUpdated`).
- ✅ Popup pre-fills detected title under the URL row.
- ⬜ Manual smoke test in Chrome (requires loading the unpacked extension).

## M4 — Folder picker 🟡

- ✅ Daemon: `GET /folders` wraps `rmapi ls -r /`, cached 60 s, empty list on failure.
- ✅ Options page: `<datalist>` auto-completes the folder text input from `/folders`.
- ✅ Fallback to free-text input if daemon offline or `rmapi` missing.
- ⬜ Adapter for actual `rmapi ls` output format (current parser assumes `[d] /Path`).

## M5 — Polish ⬜

- ⬜ Real icons (commission or AI-generate at 16/32/48/128/512).
- ⬜ Screencast GIF in `chrome-extension/README.md`.
- ⬜ Manifest description i18n (`_locales/en`, `_locales/fr`).
- ⬜ Keyboard shortcut (`commands` in manifest, default `Alt+Shift+R`).

## M6 — Distribution 🧊

- 🧊 Chrome Web Store listing (privacy policy, screenshots, real icons).
- 🧊 Signed update channel for the daemon (Homebrew tap or wheel on PyPI with launchd plist).
- 🧊 Firefox port (MV3 once stable on FF).

---

## Cross-cutting

- ⬜ ADR-003: localhost HTTP daemon vs native messaging (capture rationale from PRD §4).
- ⬜ Threat model: token leak via popup screenshot? Browser extension API surface?
- ⬜ Telemetry stance: explicit "no network calls outside ArXiv/reMarkable" assertion in extension README.

## Definition of done (per milestone)

A milestone is done when:

1. All checkboxes flipped.
2. `pytest` green (where tests apply).
3. Manual smoke test recorded (URL + screenshot or log excerpt).
4. PRD §8 milestone line updated with completion date.
