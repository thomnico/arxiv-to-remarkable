# PRD — Chrome Extension: ArXiv → reMarkable

**Status**: Draft
**Owner**: Nicolas Thomas
**Created**: 2026-04-29
**Related**: [PRD.md](../PRD.md), [ADR-002-pdf-output-format.md](./ADR-002-pdf-output-format.md)

---

## 1. Problem

Reading an ArXiv paper on reMarkable today: copy URL → terminal → `arxiv2rm convert` → `rmapi put` (with `RMAPI_FORCE_SCHEMA_VERSION=4`). Friction kills usage.

**Goal**: one click in Chrome → paper on reMarkable in <60s.

## 2. Users

Solo researcher / engineer. Already has `arxiv2rm` + `rmapi` working locally. Reads papers daily, owns reMarkable.

## 3. Scope (v1)

### In

- Chrome MV3 extension, browser action button.
- Auto-detect ArXiv pages (`arxiv.org/abs/*`, `arxiv.org/pdf/*`).
- Detect IEEE / generic PDF URLs (best effort).
- One-click "Send to reMarkable".
- Progress indicator (download → convert → upload).
- Toast on success, error message + retry on failure.
- Local options page: font size (12/14/16/18), output dir, reMarkable folder.

### Out (v1)

- Mobile/Safari/Firefox.
- Cloud-hosted converter.
- Auth UI for reMarkable Cloud (uses existing `rmapi` config).
- Batch / queue.
- Annotations sync back.

## 4. Architecture

```
[Chrome ext] ──HTTP──▶ [Local daemon :7842] ──exec──▶ [arxiv2rm] ──▶ [rmapi]
```

**Chrome extension** (TS + Vite + Plasmo or vanilla MV3):

- `background.js`: handles button click, sends URL to daemon.
- `content.js`: detects ArXiv pages, badges icon.
- `popup.html`: status + manual URL input.
- `options.html`: font size, daemon URL, folder.

**Local daemon** (Python FastAPI, packaged with arxiv2rm):

- `POST /convert {url, options}` → returns job_id.
- `GET /status/{job_id}` → `{stage, progress, error?, output_path?}`.
- `POST /push/{job_id}` → triggers `rmapi put` with `RMAPI_FORCE_SCHEMA_VERSION=4`.
- Bind `127.0.0.1:7842` only. CORS: `chrome-extension://<ID>` only.
- Auth: bearer token in `~/.arxiv2rm/daemon.token`, written on first run, configured in extension options.
- New CLI: `arxiv2rm daemon start|stop|status`.

**Why local daemon, not native messaging?**

- Easier dev/debug (curl-able).
- Can be reused by CLI / future iOS shortcut / web UI.
- Tradeoff: needs port + token. Acceptable for solo user.

## 5. UX flows

### Happy path

1. User on `https://arxiv.org/abs/2604.22446v1`. Icon badge: green dot.
2. Click icon → popup: paper title detected, "Send to reMarkable" button.
3. Click button → progress: `Downloading… 12% / Converting… 67% / Uploading…`
4. Toast: "✓ Sent to reMarkable" with link to file.
5. Total: 30–60s for typical ArXiv paper.

### Error path

- Daemon offline → popup shows "Daemon not running. [Start] [Help]".
- Conversion fails → error excerpt + "Open log" button.
- Upload fails → "Retry upload" (skip re-conversion).

### Non-ArXiv PDF

- Icon stays grey on non-ArXiv pages.
- Right-click any PDF link → "Send to reMarkable" context menu.

## 6. Non-functional

- **Latency**: <60s P50, <120s P95 for ArXiv papers ≤30 pages.
- **Privacy**: zero cloud calls except ArXiv + reMarkable. No telemetry.
- **Security**:
  - Daemon binds localhost only.
  - Bearer token auth (random 32-byte hex).
  - Extension validates daemon TLS-fingerprint? — N/A localhost; rely on token.
  - URL allowlist: arxiv.org, ieee.org, *.pdf only.
- **Resilience**: daemon survives `arxiv2rm` crashes; jobs persisted to `~/.arxiv2rm/jobs/`.

## 7. Tech choices

| Concern | Choice | Reason |
|---|---|---|
| Manifest | MV3 | Chrome requires it |
| Ext stack | Vanilla TS + Vite | No framework needed |
| Daemon | FastAPI | Already Python; async; auto OpenAPI |
| IPC | HTTP/JSON | Debuggable via curl |
| Job store | SQLite (`jobs.db`) | Survives daemon restart |
| Auth | Bearer token | Simple, sufficient for localhost |
| Distribution | Chrome Web Store (later); unpacked dev install (v1) | Skip review for solo use |

## 8. Milestones

- **M1 (1d)**: Daemon `POST /convert` returns synchronous job; `arxiv2rm daemon` CLI.
- **M2 (2d)**: MV3 extension skeleton, popup, calls daemon.
- **M3 (1d)**: Async jobs + progress polling.
- **M4 (1d)**: rmapi integration with `RMAPI_FORCE_SCHEMA_VERSION=4`; folder selection.
- **M5 (0.5d)**: Options page, error UX, badges.
- **M6 (0.5d)**: README + GIF demo.

Total: ~6 working days.

## 9. Open questions

- Should daemon auto-start via launchd on macOS, or manual `arxiv2rm daemon start`?
- Should we expose a "preview PDF before push" step?
- Where to default reMarkable folder: root or `/ArXiv/`?
- How to handle papers >30 pages (chunked conversion progress)?
- Fallback if `RMAPI_FORCE_SCHEMA_VERSION=4` stops working: detect schema dynamically?
- Native messaging host as future migration path if port conflicts arise?
