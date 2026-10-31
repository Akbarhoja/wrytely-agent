import { probeDetails } from "./details.mjs";
import { ProbeError } from "./probe.mjs";
import { config } from "./scope.mjs";

let running = false;
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (
    sender.id !== chrome.runtime.id ||
    sender.url !== chrome.runtime.getURL("popup.html") ||
    message?.kind !== "run"
  )
    return;
  if (running) {
    respond({ state: "busy" });
    return;
  }
  running = true;
  (async () => {
    await chrome.action.setBadgeText({ text: "RUN" });
    let report;
    try {
      report = await probeDetails(config);
    } catch (error) {
      report = {
        state: "blocked",
        reason: error instanceof ProbeError ? error.code : "probe_failed",
      };
    }
    await chrome.action.setBadgeText({
      text: report.state === "blocked" ? "STOP" : "READ",
    });
    return report;
  })()
    .then(respond, () => respond({ state: "blocked", reason: "probe_failed" }))
    .finally(() => {
      running = false;
    });
  return true;
});
