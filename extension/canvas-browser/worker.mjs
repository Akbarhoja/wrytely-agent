import { registerCanvasHost } from "./canvas-pairing/host-events.mjs";
import { makeFileTransport } from "./canvas-pairing/file-storage.mjs";
import { config } from "./config.mjs";

// Registration reconciles persisted preferences; a fresh profile stays inactive.
registerCanvasHost({
  chrome,
  ...config,
  fileTransport: makeFileTransport(
    chrome.webRequest,
    chrome.runtime.getURL("").replace(/\/$/, ""),
  ),
});
