import { mountControls } from "./ui.mjs";
import { config } from "./config.mjs";

// This entrypoint runs only inside the packaged extension page.
const controls = mountControls({
  document,
  send: (message) => chrome.runtime.sendMessage(message),
  openOptions: () => chrome.runtime.openOptionsPage(),
});
document.getElementById("scope").textContent =
  `Connector ${chrome.runtime.getManifest().version}. Canvas: ${new URL(config.canvasOrigin).hostname}. Wrytely service: ${new URL(config.apiOrigin).hostname}.`;
window.addEventListener("pagehide", () => controls.dispose(), { once: true });
