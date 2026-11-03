// Connector availability only. No installation, model scheduler or second source journal.
import { createPairingClient } from "./client.mjs";
import { checkedOrigin } from "../canvas-feasibility/probe.mjs";
import { DOCUMENT_COLLECTION_ERRORS } from "./document-collector.mjs";
import { discoveryConflicts } from "./discovery.mjs";
import { RECOVERY_DIAGNOSTIC_CODES } from "./collector.mjs";

export const HOST_ALARMS = Object.freeze({
  periodic: "wrytely.canvas.host.periodic.v1",
  continuation: "wrytely.canvas.host.continuation.v1",
});
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const transient = new Set([
  "rate_limited",
  "provider_unavailable",
  "provider_error",
  "network_or_redirect_blocked",
  "discovery_outcome_unknown",
  "file_network_failed",
  "file_access_failed",
]);
const reasons = new Set([
  ...RECOVERY_DIAGNOSTIC_CODES,
  ...DOCUMENT_COLLECTION_ERRORS,
  ...discoveryConflicts.map((code) => `discovery_${code}`),
  "collector_failed",
  ...transient,
  "login_required",
  "permission_denied",
  "canvas_account_changed",
  "canvas_session_unavailable",
  "reconnect_required",
  "discovery_context_changed",
  "discovery_journal_invalid",
  "storage_cleanup_required",
  "discovery_reconciliation_required",
]);
const stopReasons = new Set([...reasons, "host_failed"]);
const error = (code) => Object.assign(new Error(code), { code });

export function createCanvasHost({
  apiOrigin,
  canvasOrigin,
  storageArea,
  alarms,
  fileTransport,
  client,
  burstSteps = 1,
  now = Date.now,
  randomUUID = () => crypto.randomUUID(),
}) {
  for (const value of [apiOrigin, canvasOrigin]) {
    if (checkedOrigin(value) !== value) throw error("invalid_configuration");
  }
  if (
    !Number.isInteger(burstSteps) ||
    burstSteps < 1 ||
    burstSteps > 100 ||
    !storageArea ||
    !alarms ||
    ["get", "set", "setAccessLevel"].some(
      (k) => typeof storageArea[k] !== "function",
    ) ||
    ["get", "create", "clear"].some((k) => typeof alarms[k] !== "function")
  )
    throw error("invalid_configuration");
  client ??= createPairingClient({
    apiOrigin,
    canvasOrigin,
    storageArea,
    fileTransport,
  });
  const key = `wrytely.canvas.host.v1:${apiOrigin}:${canvasOrigin}`;
  let busy = false,
    identityBusy = false,
    localPause = false,
    queue = Promise.resolve();
  let view = { state: "paused", reason: null, course_count: 0, coverage: null };
  const serial = (operation) => {
    const result = queue.then(operation);
    queue = result.catch(() => {});
    return result;
  };
  const fresh = () => ({
    version: 1,
    enabled: false,
    control_epoch: null,
    failures: 0,
    next_attempt_at: 0,
    device_public_id: null,
    stop_reason: null,
  });
  async function load() {
    let value;
    try {
      await storageArea.setAccessLevel({ accessLevel: "TRUSTED_CONTEXTS" });
      value = (await storageArea.get(key))[key];
    } catch {
      throw error("storage_unavailable");
    }
    if (value === undefined) return fresh();
    if (
      !value ||
      typeof value !== "object" ||
      Object.keys(value)
        .filter((k) => k !== "stop_reason")
        .sort()
        .join() !==
        Object.keys(fresh())
          .filter((k) => k !== "stop_reason")
          .sort()
          .join() ||
      (value.stop_reason !== undefined &&
        value.stop_reason !== null &&
        (!stopReasons.has(value.stop_reason) || value.enabled !== false)) ||
      value.version !== 1 ||
      typeof value.enabled !== "boolean" ||
      !(value.control_epoch === null || uuid.test(value.control_epoch)) ||
      (value.enabled && !value.control_epoch) ||
      !Number.isSafeInteger(value.failures) ||
      value.failures < 0 ||
      value.failures > 16 ||
      !Number.isSafeInteger(value.next_attempt_at) ||
      value.next_attempt_at < 0 ||
      !(value.device_public_id === null || uuid.test(value.device_public_id))
    )
      throw error("host_state_invalid");
    return { ...value, stop_reason: value.stop_reason ?? null };
  }
  async function save(value) {
    try {
      await storageArea.set({ [key]: value });
    } catch {
      throw error("storage_unavailable");
    }
  }
  function nextEpoch() {
    const value = randomUUID();
    if (typeof value !== "string" || !uuid.test(value))
      throw error("host_state_invalid");
    return value;
  }
  function statusOf(p, override = {}) {
    return {
      ...view,
      ...(!p.enabled && p.stop_reason
        ? { state: "blocked", reason: p.stop_reason }
        : {}),
      enabled: p.enabled && !localPause,
      running: busy,
      retry_after_ms: Math.max(0, p.next_attempt_at - now()),
      ...override,
    };
  }
  function blocked(e, durable = false) {
    const code = ["storage_unavailable", "host_state_invalid"].includes(e?.code)
      ? e.code
      : "host_failed";
    return {
      state: "blocked",
      reason: code,
      enabled: false,
      running: busy,
      durable,
    };
  }
  async function clear() {
    const results = await Promise.allSettled(
      Object.values(HOST_ALARMS).map((name) => alarms.clear(name)),
    );
    return results.every((r) => r.status === "fulfilled");
  }
  async function schedule(p, continuation = true) {
    if (!p.enabled || localPause) return;
    if (!(await alarms.get(HOST_ALARMS.periodic)))
      await alarms.create(HOST_ALARMS.periodic, { periodInMinutes: 30 });
    if (continuation)
      await alarms.create(HOST_ALARMS.continuation, {
        when: Math.max(now() + 30000, p.next_attempt_at),
      });
    else await alarms.clear(HOST_ALARMS.continuation);
  }
  async function safeControl(operation) {
    return serial(async () => {
      try {
        return await operation();
      } catch (e) {
        localPause = true;
        await clear();
        return blocked(e);
      }
    });
  }
  async function status() {
    return safeControl(async () => {
      const p = await load();
      return statusOf(
        p,
        (!p.enabled || localPause) && !p.stop_reason
          ? { state: "paused" }
          : p.next_attempt_at > now()
            ? { state: "cooldown" }
            : {},
      );
    });
  }
  async function enable() {
    return safeControl(async () => {
      const p = await load();
      if (identityBusy)
        return statusOf(p, { state: "busy", reason: "identity_in_progress" });
      const next = {
        ...p,
        enabled: true,
        control_epoch: nextEpoch(),
        failures: 0,
        next_attempt_at: 0,
        stop_reason: null,
      };
      await save(next);
      localPause = false;
      view = { ...view, state: "ready", reason: null };
      await schedule(next);
      return statusOf(next);
    });
  }
  async function disable() {
    // Stop new operations synchronously, even while another source request awaits IO.
    localPause = true;
    return serial(async () => {
      let next;
      try {
        const p = await load();
        next = {
          ...p,
          enabled: false,
          control_epoch: nextEpoch(),
          failures: 0,
          next_attempt_at: 0,
          stop_reason: null,
        };
        await save(next);
      } catch (e) {
        await clear();
        return blocked(e);
      }
      const alarmCleanup = await clear();
      view = { ...view, state: "paused", reason: null };
      return statusOf(next, { durable: true, alarm_cleanup: alarmCleanup });
    });
  }
  async function reconcile() {
    return safeControl(async () => {
      const p = await load();
      if (p.enabled && !localPause) {
        await schedule(p);
        view = {
          ...view,
          state: p.next_attempt_at > now() ? "cooldown" : "ready",
        };
      } else await clear();
      return statusOf(p);
    });
  }
  async function collectStep() {
    let start;
    try {
      start = await serial(() => load());
      if (!start.enabled || localPause)
        return statusOf(start, start.stop_reason ? {} : { state: "paused" });
      if (start.next_attempt_at > now())
        return statusOf(start, { state: "cooldown" });
      let result;
      try {
        const current = await client.readDiscoveryStatus();
        const dispatch = await serial(async () => {
          const latest = await load();
          if (
            localPause ||
            !latest.enabled ||
            latest.control_epoch !== start.control_epoch
          )
            return {
              cancelled: true,
              status: statusOf(latest, {
                state: latest.enabled && !localPause ? "ready" : "paused",
              }),
            };
          // Start synchronously under the control queue, but await outside it so pause remains responsive.
          return {
            completion:
              current.state === "finished"
                ? client.beginDiscovery()
                : (
                    client.collectDocumentPage ?? client.collectAssignmentPage
                  ).call(client),
          };
        });
        if (dispatch.cancelled) return dispatch.status;
        result = await dispatch.completion;
        if (current.state === "finished")
          result = { state: "progress", action: "begin" };
      } catch (e) {
        result = {
          state: "blocked",
          reason: reasons.has(e?.code) ? e.code : "host_failed",
        };
      }
      return await serial(async () => {
        const p = await load();
        if (p.control_epoch !== start.control_epoch || localPause || !p.enabled)
          return statusOf(p, {
            state: p.enabled && !localPause ? "ready" : "paused",
          });
        let next = { ...p, failures: 0, next_attempt_at: 0 };
        if (result?.state === "blocked") {
          const reason = reasons.has(result.reason)
            ? result.reason
            : "host_failed";
          if (transient.has(reason)) {
            next.failures = Math.min(16, p.failures + 1);
            next.next_attempt_at =
              now() +
              Math.min(
                6 * 60 * 60 * 1000,
                5 * 60 * 1000 * 2 ** (next.failures - 1),
              );
            view = { ...view, state: "cooldown", reason };
          } else {
            next.enabled = false;
            next.stop_reason = reason;
            next.control_epoch = nextEpoch();
            view = { ...view, state: "blocked", reason };
          }
        } else if (
          ["progress", "finished", "awaiting_resources"].includes(result?.state)
        ) {
          view = {
            state: result.state,
            reason: null,
            course_count:
              Number.isSafeInteger(result.seen_count) && result.seen_count >= 0
                ? result.seen_count
                : 0,
            coverage: ["partial", "complete"].includes(result.coverage)
              ? result.coverage
              : null,
          };
          if (result.action === "begin") view.action = "begin";
        } else {
          next.enabled = false;
          next.stop_reason = "host_failed";
          next.control_epoch = nextEpoch();
          view = { ...view, state: "blocked", reason: "host_failed" };
        }
        await save(next);
        if (next.enabled)
          await schedule(
            next,
            !["finished", "awaiting_resources"].includes(view.state),
          );
        else await clear();
        return statusOf(next);
      });
    } catch (e) {
      localPause = true;
      await clear();
      return blocked(e);
    }
  }
  async function collect() {
    if (busy) return { state: "busy", running: true };
    busy = true;
    try {
      const deadline = now() + 15000;
      let result;
      for (let step = 0; step < burstSteps; step++) {
        result = await collectStep();
        // Check the soft event budget between durable steps. A step keeps its
        // existing request deadlines and fences; finish/pause/failure stops now.
        if (
          result.state !== "progress" ||
          result.enabled !== true ||
          now() >= deadline
        )
          break;
      }
      return { ...result, running: false };
    } finally {
      busy = false;
    }
  }
  async function identity(action, code) {
    if (busy) return { state: "busy", running: true };
    busy = true;
    identityBusy = true;
    try {
      const input = await serial(async () => {
        const p = await load();
        if (p.enabled) throw error("pause_required");
        if (
          action === "pair" &&
          (typeof code !== "string" || !/^[A-Za-z0-9_-]{32}$/.test(code))
        )
          throw error("invalid_pairing_input");
        if (!p.device_public_id) {
          p.device_public_id = nextEpoch();
          await save(p);
        }
        return p;
      });
      const result =
        action === "pair"
          ? await client.redeem({
              code,
              devicePublicId: input.device_public_id,
            })
          : await client.bindCurrentSession();
      return {
        state: [
          "pending_identity",
          "connected",
          "active",
          "reconnect_required",
        ].includes(result?.state)
          ? result.state
          : "identity_updated",
        enabled: false,
      };
    } catch (e) {
      return {
        state: "blocked",
        reason: [
          "pause_required",
          "invalid_pairing_input",
          "storage_unavailable",
          "host_state_invalid",
        ].includes(e?.code)
          ? e.code
          : reasons.has(e?.code)
            ? e.code
            : "identity_failed",
        ...(e?.code === "pause_required" ? {} : { enabled: false }),
      };
    } finally {
      busy = false;
      identityBusy = false;
    }
  }
  return Object.freeze({
    status,
    enable,
    disable,
    reconcile,
    collect,
    pair: (code) => identity("pair", code),
    bind: () => identity("bind"),
  });
}
