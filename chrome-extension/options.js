const FIELDS = ["daemonUrl", "token", "fontSize", "deviceModel", "folder"];
const DEFAULTS = {
  daemonUrl: "http://127.0.0.1:7842",
  token: "",
  fontSize: 14,
  deviceModel: "rmpro",
  folder: "/ArXiv/",
};

async function load() {
  const s = await chrome.storage.sync.get(DEFAULTS);
  for (const k of FIELDS) document.getElementById(k).value = s[k] ?? DEFAULTS[k];
  populateFolders(s.daemonUrl || DEFAULTS.daemonUrl, s.token || DEFAULTS.token);
}

async function populateFolders(daemonUrl, token) {
  if (!token) return;
  try {
    const res = await fetch(`${daemonUrl}/folders`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;
    const { folders = [] } = await res.json();
    const dl = document.getElementById("folders");
    dl.replaceChildren(
      ...folders.map((f) => {
        const opt = document.createElement("option");
        opt.value = f;
        return opt;
      })
    );
  } catch {
    // ignore; free-text input still works
  }
}

async function save() {
  const payload = {};
  for (const k of FIELDS) {
    const el = document.getElementById(k);
    payload[k] = k === "fontSize" ? parseInt(el.value, 10) : el.value.trim();
  }
  await chrome.storage.sync.set(payload);
  const msg = document.getElementById("msg");
  msg.textContent = "Saved.";
  setTimeout(() => (msg.textContent = ""), 1500);
}

document.getElementById("save").addEventListener("click", save);
load();
