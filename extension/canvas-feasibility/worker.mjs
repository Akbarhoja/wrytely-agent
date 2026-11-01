import { probeCanvas, ProbeError } from "./probe.mjs";
import { config } from "./scope.mjs";

let running = false;
chrome.action.onClicked.addListener(async () => {
  if (running) return;
  running = true;
  await chrome.action.setBadgeText({ text: "RUN" });
  try {
    const report = await probeCanvas(config);
    console.info("Wrytely feasibility (counts only)", report);
    await chrome.action.setBadgeText({ text: "READ" });
  } catch (error) {
    console.info("Wrytely feasibility", {
      state: "blocked",
      reason: error instanceof ProbeError ? error.code : "probe_failed",
    });
    await chrome.action.setBadgeText({ text: "STOP" });
  } finally {
    running = false;
  }
});
