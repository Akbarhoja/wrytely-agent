import {
  CDN_ORIGIN,
  FILE_ORIGIN,
  makeFileTransport,
  probeDetails,
} from "./details.mjs";
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
      const granted = config.fileSamples.length
        ? await chrome.permissions.contains({ origins: [`${FILE_ORIGIN}/*`] })
        : null;
      const cdnGranted = config.fileSamples.length
        ? await chrome.permissions.contains({ origins: [`${CDN_ORIGIN}/*`] })
        : null;
      if (granted === false || cdnGranted === false)
        throw new ProbeError("file_host_permission_missing");
      const transport = config.fileSamples.length
        ? makeFileTransport(
            chrome.webRequest,
            chrome.runtime.getURL("").replace(/\/$/, ""),
          )
        : undefined;
      report = await probeDetails(config, fetch, transport);
      if (cdnGranted !== null) report.cdnHostPermissionGranted = cdnGranted;
      if (granted !== null) report.fileHostPermissionGranted = granted;
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
