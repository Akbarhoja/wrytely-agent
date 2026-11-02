// Called by a future packaged worker; importing this module installs no listeners.
import { createCanvasHost, HOST_ALARMS } from "./host.mjs";

export const HOST_MESSAGE = "wrytely.canvas.host.v1";
const registrations = new WeakMap();
const commands = new Set([
  "status",
  "enable",
  "disable",
  "collect",
  "pair",
  "bind",
]);
const failed = () => ({
  state: "blocked",
  reason: "host_failed",
  enabled: false,
});

export function registerCanvasHost({
  chrome,
  apiOrigin,
  canvasOrigin,
  host,
  fileTransport,
  burstSteps = 1,
}) {
  const prior = registrations.get(chrome);
  if (prior) {
    if (
      prior.apiOrigin !== apiOrigin ||
      prior.canvasOrigin !== canvasOrigin ||
      prior.injected !== host ||
      prior.burstSteps !== burstSteps
    )
      throw Error("host_already_registered");
    return prior.registration;
  }
  const controller =
    host ??
    createCanvasHost({
      apiOrigin,
      canvasOrigin,
      storageArea: chrome.storage.local,
      alarms: chrome.alarms,
      fileTransport,
      burstSteps,
    });
  const trustedPages = new Set(
    ["popup.html", "options.html"].map((path) => chrome.runtime.getURL(path)),
  );
  function valid(message, sender) {
    if (
      !sender ||
      sender.id !== chrome.runtime.id ||
      "tab" in sender ||
      !trustedPages.has(sender.url)
    )
      return false;
    if (
      !message ||
      typeof message !== "object" ||
      Array.isArray(message) ||
      message.type !== HOST_MESSAGE ||
      !commands.has(message.action)
    )
      return false;
    const keys = Object.keys(message).sort().join();
    return message.action === "pair"
      ? keys === "action,code,type" &&
          typeof message.code === "string" &&
          /^[A-Za-z0-9_-]{32}$/.test(message.code)
      : keys === "action,type";
  }
  const invoke = async (action, arg) => {
    try {
      return await controller[action](arg);
    } catch {
      return failed();
    }
  };
  function onMessage(message, sender, sendResponse) {
    if (!valid(message, sender)) return false;
    void invoke(message.action, message.code).then((value) => {
      try {
        sendResponse(value);
      } catch {
        /* Popup may have closed. No private logging. */
      }
    });
    return true;
  }
  const onAlarm = (alarm) =>
    Object.values(HOST_ALARMS).includes(alarm?.name)
      ? invoke("collect")
      : undefined;
  const onStartup = () => invoke("reconcile");
  chrome.runtime.onMessage.addListener(onMessage);
  chrome.runtime.onStartup.addListener(onStartup);
  chrome.runtime.onInstalled.addListener(onStartup);
  chrome.alarms.onAlarm.addListener(onAlarm);
  const registration = Object.freeze({
    host: controller,
    ready: invoke("reconcile"),
    dispose() {
      chrome.runtime.onMessage.removeListener(onMessage);
      chrome.runtime.onStartup.removeListener(onStartup);
      chrome.runtime.onInstalled.removeListener(onStartup);
      chrome.alarms.onAlarm.removeListener(onAlarm);
      if (registrations.get(chrome)?.registration === registration)
        registrations.delete(chrome);
    },
  });
  registrations.set(chrome, {
    apiOrigin,
    canvasOrigin,
    injected: host,
    burstSteps,
    registration,
  });
  return registration;
}
