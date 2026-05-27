# PRD — Chrome Extension: ArXiv → reMarkable

**Status**: Scaffolded (M0 done)
**Owner**: Nicolas Thomas
**Created**: 2026-04-29
**Last updated**: 2026-05-22
**Related**: [PRD.md](../PRD.md), [ADR-002-pdf-output-format.md](./ADR-002-pdf-output-format.md), [TASKS-chrome-extension.md](./TASKS-chrome-extension.md)

---

## 1. Problem

Reading an ArXiv paper on reMarkable today: copy URL → terminal → `arxiv2rm convert` → `rmapi put`. Friction kills usage.

**Goal**: one click in Chrome → paper on reMarkable in <60s.

## 2. Users

Solo researcher / engineer. Already has `arxiv2rm` + `rmapi` working locally. Reads papers daily, owns reMarkable (1, 2, or Paper Pro).

## 3. Scope (v1)

### In

- Chrome MV3 extension, action button.
- Auto-detect `arxiv.org/abs/*`, `arxiv.org/pdf/*`.
- Right-click any `*.pdf` link → "Send to reMarkable".
- One-click trigger: download → convert → upload.
- Popup with stage + progress bar; OS notifications on done/error.
- Options: daemon URL, bearer token, font size, device (`rm1|rm2|rmpro`), reMarkable folder.

### Out (v1)

- Firefox/Safari/mobile.
- Cloud-hosted converter.
- Auth UI for reMarkable Cloud (reuses existing `rmapi` config).
- Batch queue, history, retry UI beyond reload.
- Annotations sync back from device.

## 4. Architecture

```
[Chrome ext] ──HTTP/JSON──▶ [arxiv2rm-daemon :7842] ──subprocess──▶ [arxiv2rm convert] ──▶ [rmapi put]
```

### Local daemon (`src/arxiv2rm/daemon/`)

FastAPI app, bound to `127.0.0.1:7842` only.

| Endpoint | Body | Returns |
|---|---|---|
| `GET /health` | — | `{status, version}` |
| `POST /convert` | `{url, font_size, device_model, columns}` | `{job_id, stage}` |
| `GET /status/{job_id}` | — | full `Job` (stage, progress, output_path, error) |
| `POST /push/{job_id}` | `{folder}` | `{job_id, stage:"pushing"}` |

- **Auth**: `Authorization: Bearer <token>`. Token = 32 random bytes hex, stored at `~/.arxiv2rm/daemon.token` (chmod 0600). Created on first run.
- **CORS**: regex `chrome-extension://.*`, methods `GET POST`, headers `Authorization Content-Type`.
- **Jobs**: in-memory dict + JSON spill at `~/.arxiv2rm/jobs/<id>.json` (survives daemon restart for inspection; not yet reloaded).
- **Subprocess**: argv lists (no shell). `rmapi` schema version is **not** forced — the reMarkable cloud rotates the expected version (a hardcoded `4` is now rejected with `wrong schema got 4, expected: 3`). The daemon inherits `RMAPI_FORCE_SCHEMA_VERSION` from its environment if the user pins it; otherwise rmapi auto-detects.
- **CLI entry point**: `arxiv2rm-daemon` (uvicorn).

### Chrome extension (`chrome-extension/`)

Vanilla MV3 (no bundler, no framework).

| File | Role |
|---|---|
| `manifest.json` | MV3, action + content script + context menu. Host perms: `127.0.0.1:7842/*`, `arxiv.org/*`. |
| `background.js` | Service worker. `startJob(url)` → POST `/convert` → poll `/status` → POST `/push` → poll `/status` → notify. |
| `content.js` | Detects `arxiv.org/(abs\|pdf)/*` (placeholder — badge update is M5). |
| `popup.{html,js,css}` | Per-tab UI: health dot, current URL, Send button, stage + progress bar, error pane. |
| `options.{html,js}` | Daemon URL, bearer token, font size, device, folder. `chrome.storage.sync`. |
| `icons/{16,48,128}.png` | Placeholders (rM glyph on blue). |

### Why local HTTP daemon (not native messaging)

- Curl-able → easier dev/debug.
- Reusable from CLI, future iOS Shortcut, web UI.
- Tradeoff: port + token. Acceptable for solo user.

## 5. UX flows

### Happy path

1. User on `https://arxiv.org/abs/2510.17521v1`. Health dot green.
2. Click toolbar icon → popup shows URL + **Send to reMarkable**.
3. Click → stage cycles `downloading → converting → converted → pushing → done`. Progress 10 → 100.
4. OS notification: "Sent to reMarkable — /ArXiv/<filename>.pdf".

### Error paths

- Daemon down → health dot red, popup shows error text, Send disabled until reload.
- Convert fails → stage=`error`, popup displays last 2 KB of subprocess output.
- `rmapi` missing → stage=`error`, message "rmapi binary not found in PATH".

## 6. Non-functional

- **Latency**: <60s P50, <120s P95 for ArXiv papers ≤30 pages.
- **Privacy**: zero outbound calls except ArXiv + reMarkable. No telemetry.
- **Security**:
  - Daemon binds `127.0.0.1` only.
  - Bearer token, constant-time compared? — current impl uses `==` (TODO: `secrets.compare_digest`).
  - URL allowlist enforced at extension level (Send button disabled off-allowlist).
- **Resilience**: jobs persisted to JSON; daemon restart loses in-flight progress but not history.

## 7. Tech choices

| Concern | Choice | Reason |
|---|---|---|
| Manifest | MV3 | Chrome requirement. |
| Ext stack | Vanilla TS-less JS + Vite-free | Keep scaffold zero-build. |
| Daemon | FastAPI + uvicorn | Already Python; async; auto OpenAPI at `/docs`. |
| IPC | HTTP/JSON | Debuggable via curl. |
| Job store | In-memory dict + JSON spill | Minimal; SQLite later if needed. |
| Auth | Bearer token | Sufficient for localhost. |
| Distribution | Unpacked dev install (v1); Chrome Web Store later | Skip review for solo use. |

## 8. Milestones

- **M0 — Scaffold (done, 2026-05-22)**: daemon endpoints, MV3 extension shell, options page, README, icons.
- **M1 — Wire end-to-end (1d)**: install `[daemon]` extra, manual run-through arxiv abs URL → reMarkable. Fix surprises.
- **M2 — Robustness (1d)**: `secrets.compare_digest`, daemon `status|stop`, better error parsing, rate-limit retries.
- **M3 — Badge + content script (0.5d)**: green/grey icon badge driven by `content.js` detection.
- **M4 — Folder picker (0.5d)**: option to pick remote folder from rmapi listing.
- **M5 — Polish (0.5d)**: real icons, screencast GIF, packaging README.
- **M6 — Chrome Web Store (deferred)**: optional, requires real icons + privacy policy.

Total to "shippable to self": ~3 working days from M0.

## 9. Open questions

- Auto-start daemon via launchd, or document manual `arxiv2rm-daemon &`?
- Preview PDF step before push? (Current: push is implicit after convert.)
- Default reMarkable folder: `/` or `/ArXiv/`? (Current default: `/ArXiv/`.)
- Papers >30 pages: keep single progress event or chunk?
- ~~Fallback if `RMAPI_FORCE_SCHEMA_VERSION=4` stops working~~ — **observed 2026-05-22**: cloud now expects schema 3. Daemon no longer forces the version; rmapi auto-detects. Revisit if rmapi's default ever lags the cloud again.
- Should the daemon also expose `GET /jobs` for a "recent" list in the popup?

## 10. References

- [TASKS-chrome-extension.md](./TASKS-chrome-extension.md) — actionable task breakdown.
- Scaffold tree:
  - `chrome-extension/` (manifest, background, content, popup, options, icons)
  - `src/arxiv2rm/daemon/` (server, jobs, auth, cli_daemon)
