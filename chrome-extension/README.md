# ArXiv → reMarkable (Chrome extension)

One-click "Send to reMarkable" from any ArXiv page. Talks to the local
`arxiv2rm` daemon, which runs `arxiv2rm convert` then `rmapi put`.

## Install (developer mode)

1. Install + start the daemon:

   ```bash
   pip install -e '.[daemon]'
   arxiv2rm-daemon            # prints token + listens on 127.0.0.1:7842
   ```

2. Open `chrome://extensions`, enable **Developer mode**, click
   **Load unpacked**, and select this `chrome-extension/` folder.

3. Open the extension **Options** page. Paste the token printed by the
   daemon (also at `~/.arxiv2rm/daemon.token`). Pick font size, device, and
   reMarkable folder. Save.

4. Navigate to `https://arxiv.org/abs/<id>` → click the toolbar icon →
   **Send to reMarkable**. Watch the progress bar.

## Files

| File | Role |
|---|---|
| `manifest.json` | MV3 manifest, action + content script + context menu. |
| `background.js` | Service worker. Calls daemon, polls jobs, fires notifications. |
| `content.js` | Detects ArXiv pages to enable the action. |
| `popup.html/js/css` | Per-tab UI: status, progress, send button. |
| `options.html/js` | Daemon URL, bearer token, font size, device, folder. |
| `icons/` | Placeholder icons (rM glyph on blue). Replace before publishing. |

## Endpoints used

- `GET  /health`
- `POST /convert {url, font_size, device_model, columns}`
- `GET  /status/{job_id}`
- `POST /push/{job_id} {folder}`

All requests carry `Authorization: Bearer <token>`.
