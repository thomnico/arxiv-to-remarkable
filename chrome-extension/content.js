// Detect ArXiv abstract/PDF pages and notify the service worker so the toolbar
// icon badge flips to green.

(function () {
  const isAbs = /^https:\/\/arxiv\.org\/abs\//.test(location.href);
  const isPdf = /^https:\/\/arxiv\.org\/pdf\//.test(location.href);
  if (!isAbs && !isPdf) return;

  const titleEl = document.querySelector("h1.title");
  const title = titleEl
    ? titleEl.textContent.replace(/^Title:\s*/, "").trim()
    : document.title;

  chrome.runtime.sendMessage({
    type: "page-detected",
    url: location.href,
    title,
  });
})();
