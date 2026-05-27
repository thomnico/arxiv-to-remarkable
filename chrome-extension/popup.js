const $ = (id) => document.getElementById(id);

async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab?.url || "";
  $("url").textContent = url;

  chrome.runtime.sendMessage({ type: "get-detected" }, (resp) => {
    if (resp?.detected?.title) {
      const node = document.createElement("div");
      node.className = "label";
      node.textContent = "Detected title";
      const t = document.createElement("div");
      t.style.fontSize = "12px";
      t.style.marginBottom = "6px";
      t.textContent = resp.detected.title;
      $("page").appendChild(node);
      $("page").appendChild(t);
    }
  });

  const allowed = /^https:\/\/arxiv\.org\/(abs|pdf)\//.test(url) || /\.pdf(\?|$)/i.test(url);
  $("send").disabled = !allowed;

  chrome.runtime.sendMessage({ type: "health" }, (resp) => {
    $("health").className = "dot " + (resp?.ok ? "ok" : "err");
  });

  $("send").addEventListener("click", () => start(url));
  $("open-options").addEventListener("click", (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });
}

function start(url) {
  $("send").disabled = true;
  $("status").hidden = false;
  chrome.runtime.sendMessage({ type: "send-current-url", url }, (resp) => {
    if (!resp?.ok) return showError(resp?.error || "failed to start job");
    poll(resp.jobId);
  });
}

function poll(jobId) {
  chrome.runtime.sendMessage({ type: "get-status", jobId }, (resp) => {
    if (!resp?.ok) return showError(resp?.error || "lost daemon");
    const job = resp.job;
    $("stage").textContent = job.stage;
    $("bar").value = job.progress || 0;
    if (job.stage === "done" || job.stage === "error") {
      if (job.stage === "error") showError(job.error);
      return;
    }
    setTimeout(() => poll(jobId), 1500);
  });
}

function showError(msg) {
  $("error").hidden = false;
  $("error").textContent = msg;
  $("send").disabled = false;
}

init();
