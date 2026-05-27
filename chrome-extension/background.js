// Background service worker: wires the action click and context menu to the
// local arxiv2rm daemon. Settings live in chrome.storage.sync.

const DEFAULTS = {
  daemonUrl: "http://127.0.0.1:7842",
  token: "",
  fontSize: 14,
  deviceModel: "rmpro",
  folder: "/ArXiv/",
};

async function getSettings() {
  const stored = await chrome.storage.sync.get(DEFAULTS);
  return { ...DEFAULTS, ...stored };
}

async function daemon(path, { method = "GET", body } = {}) {
  const { daemonUrl, token } = await getSettings();
  const res = await fetch(`${daemonUrl}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

async function startJob(url) {
  const s = await getSettings();
  const { job_id } = await daemon("/convert", {
    method: "POST",
    body: {
      url,
      font_size: s.fontSize,
      device_model: s.deviceModel,
    },
  });
  notify(`Converting ${url}`, "Job started…");
  pollUntilConverted(job_id, s.folder).catch((err) =>
    notify("Conversion failed", err.message)
  );
  return job_id;
}

async function pollUntilConverted(jobId, folder) {
  for (let i = 0; i < 120; i++) {
    const job = await daemon(`/status/${jobId}`);
    if (job.stage === "error") throw new Error(job.error || "unknown error");
    if (job.stage === "converted") {
      await daemon(`/push/${jobId}`, { method: "POST", body: { folder } });
      return pollUntilDone(jobId);
    }
    await sleep(1500);
  }
  throw new Error("Timed out waiting for conversion");
}

async function pollUntilDone(jobId) {
  for (let i = 0; i < 60; i++) {
    const job = await daemon(`/status/${jobId}`);
    if (job.stage === "error") throw new Error(job.error || "push failed");
    if (job.stage === "done") {
      notify("Sent to reMarkable", job.remote_path || "");
      return job;
    }
    await sleep(1500);
  }
  throw new Error("Timed out waiting for push");
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function notify(title, message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/128.png",
    title,
    message: message?.slice(0, 240) || "",
  });
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "send-to-remarkable",
    title: "Send to reMarkable",
    contexts: ["link", "page"],
    targetUrlPatterns: ["https://arxiv.org/*", "https://*.arxiv.org/*", "*://*/*.pdf*"],
  });
});

// Cache the detected title per tab so the popup can preview it.
const detected = new Map();

function setBadge(tabId, on) {
  chrome.action.setBadgeBackgroundColor({ tabId, color: on ? "#2ea043" : [0, 0, 0, 0] });
  chrome.action.setBadgeText({ tabId, text: on ? "●" : "" });
}

chrome.tabs.onRemoved.addListener((tabId) => detected.delete(tabId));

chrome.tabs.onUpdated.addListener((tabId, info, tab) => {
  if (info.status !== "loading") return;
  if (!/^https:\/\/arxiv\.org\/(abs|pdf)\//.test(tab.url || "")) {
    detected.delete(tabId);
    setBadge(tabId, false);
  }
});

chrome.contextMenus.onClicked.addListener((info) => {
  const url = info.linkUrl || info.pageUrl;
  if (url) startJob(url);
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === "page-detected" && sender.tab?.id != null) {
    detected.set(sender.tab.id, { url: msg.url, title: msg.title });
    setBadge(sender.tab.id, true);
    sendResponse({ ok: true });
    return;
  }
  if (msg?.type === "get-detected") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tabId = tabs[0]?.id;
      sendResponse({ ok: true, detected: tabId != null ? detected.get(tabId) : null });
    });
    return true;
  }
  if (msg?.type === "send-current-url") {
    startJob(msg.url)
      .then((id) => sendResponse({ ok: true, jobId: id }))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true; // async response
  }
  if (msg?.type === "get-status") {
    daemon(`/status/${msg.jobId}`)
      .then((job) => sendResponse({ ok: true, job }))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true;
  }
  if (msg?.type === "health") {
    daemon("/health")
      .then((h) => sendResponse({ ok: true, health: h }))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true;
  }
});
