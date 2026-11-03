import { test } from "node:test";
import assert from "node:assert/strict";
import { createCanvasHost, HOST_ALARMS } from "./host.mjs";

test("background host uses the connected document collector when available", async () => {
  const f = fixture();
  let documents = 0;
  f.options.client.collectDocumentPage = async () => {
    documents++;
    return { state: "progress", action: "document_step", seen_count: 2 };
  };
  await f.host.enable();
  await f.host.collect();
  assert.equal(documents, 1);
  assert.ok(!f.events.includes("collect"));
});

function fixture() {
  const data = {},
    events = [],
    scheduled = new Map();
  let time = 1000000,
    read = { state: "active" },
    result = { state: "progress", seen_count: 2 };
  let failure,
    pending,
    failSet = false,
    failClear = false;
  const storageArea = {
    async setAccessLevel() {},
    async get(key) {
      return structuredClone({ [key]: data[key] });
    },
    async set(value) {
      if (failSet) throw Error("PRIVATE");
      events.push("persist");
      Object.assign(data, structuredClone(value));
    },
    async remove(key) {
      delete data[key];
    },
  };
  const alarms = {
    async get(name) {
      return scheduled.get(name);
    },
    async create(name, info) {
      events.push("alarm");
      scheduled.set(name, info);
    },
    async clear(name) {
      if (failClear) throw Error("PRIVATE");
      return scheduled.delete(name);
    },
  };
  const client = {
    async readDiscoveryStatus() {
      events.push("inspect");
      return read;
    },
    async beginDiscovery() {
      events.push("begin");
      return { state: "active" };
    },
    async collectAssignmentPage() {
      events.push("collect");
      if (pending) await pending;
      if (failure) throw failure;
      return result;
    },
    async redeem(value) {
      events.push(["redeem", value]);
      return { state: "pending_identity", ingestion_bearer: "PRIVATE" };
    },
    async bindCurrentSession() {
      events.push("bind");
      return { state: "connected", subject_id: "PRIVATE" };
    },
  };
  const options = {
    apiOrigin: "https://agent.example.edu",
    canvasOrigin: "https://canvas.example.edu",
    storageArea,
    alarms,
    client,
    now: () => time,
    randomUUID: () => crypto.randomUUID(),
  };
  return {
    data,
    events,
    scheduled,
    options,
    host: createCanvasHost(options),
    set read(v) {
      read = v;
    },
    set result(v) {
      result = v;
    },
    set failure(v) {
      failure = v;
    },
    set pending(v) {
      pending = v;
    },
    set failSet(v) {
      failSet = v;
    },
    set failClear(v) {
      failClear = v;
    },
    advance(ms) {
      time += ms;
    },
  };
}

test("default paused: startup/status/collect create no requests or alarms", async () => {
  const f = fixture();
  assert.equal((await f.host.reconcile()).enabled, false);
  assert.equal((await f.host.collect()).state, "paused");
  assert.equal((await f.host.status()).enabled, false);
  assert.deepEqual(f.events, []);
});
test("explicit enable persists first, restores lost alarms only when enabled", async () => {
  const f = fixture();
  await f.host.enable();
  assert.equal(f.events[0], "persist");
  assert.equal(f.scheduled.get(HOST_ALARMS.periodic).periodInMinutes, 30);
  f.scheduled.clear();
  f.events.length = 0;
  await createCanvasHost(f.options).reconcile();
  assert.equal(f.scheduled.size, 2);
  assert.ok(!f.events.includes("collect"));
  await f.host.disable();
  f.scheduled.clear();
  await createCanvasHost(f.options).reconcile();
  assert.equal(f.scheduled.size, 0);
});
test("one step uses existing pending-first collector; finished scan explicitly begins again", async () => {
  const f = fixture();
  await f.host.enable();
  f.read = { state: "pending", pending: "academic" };
  assert.equal((await f.host.collect()).state, "progress");
  assert.deepEqual(
    f.events.filter(
      (x) =>
        typeof x === "string" && ["inspect", "collect", "begin"].includes(x),
    ),
    ["inspect", "collect"],
  );
  f.read = { state: "finished" };
  assert.equal((await f.host.collect()).action, "begin");
  assert.equal(f.events.at(-2), "persist");
  assert.ok(f.events.includes("begin"));
});
test("projection omits private identifiers, source and arbitrary coverage reasons", async () => {
  const f = fixture();
  await f.host.enable();
  f.result = {
    state: "progress",
    seen_count: 2,
    coverage: "partial",
    reason: "PRIVATE",
    subject_id: "PRIVATE",
    checkpoint: "PRIVATE",
  };
  const result = await f.host.collect();
  assert.equal(result.course_count, 2);
  assert.equal(result.coverage, "partial");
  assert.ok(!JSON.stringify(result).includes("PRIVATE"));
});
test("awaiting resources does not create continuation loop; finished waits for periodic", async () => {
  for (const state of ["awaiting_resources", "finished"]) {
    const f = fixture();
    await f.host.enable();
    f.result = { state };
    assert.equal((await f.host.collect()).state, state);
    assert.equal(f.scheduled.has(HOST_ALARMS.continuation), false);
    assert.equal(f.scheduled.has(HOST_ALARMS.periodic), true);
  }
});
test("transient backoff persists across restart and caps at six hours", async () => {
  const f = fixture();
  await f.host.enable();
  f.failure = { code: "rate_limited", message: "PRIVATE" };
  assert.equal((await f.host.collect()).state, "cooldown");
  const count = f.events.filter((x) => x === "collect").length;
  assert.equal((await createCanvasHost(f.options).collect()).state, "cooldown");
  assert.equal(f.events.filter((x) => x === "collect").length, count);
  for (let i = 0; i < 12; i++) {
    f.advance(24 * 60 * 60 * 1000);
    await createCanvasHost(f.options).collect();
  }
  const status = await f.host.status();
  assert.equal(status.retry_after_ms, 6 * 60 * 60 * 1000);
  assert.ok(!JSON.stringify(status).includes("PRIVATE"));
});
test("blocked auth, corrupt journal, unknown errors pause durably without retry", async () => {
  for (const code of [
    "login_required",
    "canvas_account_changed",
    "discovery_journal_invalid",
    "discovery_replay_conflict",
    "PRIVATE",
  ]) {
    const f = fixture();
    await f.host.enable();
    f.failure = { code, message: "PRIVATE" };
    const result = await f.host.collect();
    assert.equal(result.enabled, false);
    assert.equal(result.state, "blocked");
    assert.ok(!JSON.stringify(result).includes("PRIVATE"));
    const restarted = createCanvasHost(f.options);
    assert.equal((await restarted.reconcile()).state, "blocked");
    assert.equal((await restarted.status()).reason, result.reason);
    assert.equal((await restarted.collect()).state, "blocked");
    assert.equal(f.scheduled.size, 0);
    await restarted.disable();
    assert.equal((await createCanvasHost(f.options).status()).state, "paused");
    assert.equal((await createCanvasHost(f.options).status()).reason, null);
  }
});
test("legacy preferences load without granting access; untrusted stop text fails closed", async () => {
  const f = fixture();
  await f.host.enable();
  await f.host.disable();
  const key = Object.keys(f.data)[0];
  delete f.data[key].stop_reason;
  assert.equal((await createCanvasHost(f.options).status()).state, "paused");
  assert.equal(f.scheduled.size, 0);
  f.data[key].stop_reason = "PRIVATE course content";
  const status = await createCanvasHost(f.options).status();
  assert.equal(status.reason, "host_state_invalid");
  assert.ok(!JSON.stringify(status).includes("PRIVATE"));
});
test("pause during collector prevents stale completion and duplicate calls", async () => {
  const f = fixture();
  await f.host.enable();
  let release;
  f.pending = new Promise((r) => (release = r));
  const work = f.host.collect();
  while (!f.events.includes("collect"))
    await new Promise((r) => setImmediate(r));
  assert.equal((await f.host.collect()).state, "busy");
  assert.equal((await f.host.status()).running, true);
  await f.host.disable();
  release();
  assert.equal((await work).enabled, false);
  assert.equal(f.scheduled.size, 0);
});
test("pause then enable fences old failure from disabling newly enabled host", async () => {
  const f = fixture();
  await f.host.enable();
  let release;
  f.pending = new Promise((r) => (release = r));
  f.failure = { code: "login_required" };
  const work = f.host.collect();
  while (!f.events.includes("collect"))
    await new Promise((r) => setImmediate(r));
  await f.host.disable();
  await f.host.enable();
  release();
  await work;
  assert.equal((await f.host.status()).enabled, true);
  assert.equal(f.scheduled.size, 2);
});
test("failed pause persistence reports failure; alarm clear failure cannot undo persisted pause", async () => {
  const f = fixture();
  await f.host.enable();
  f.failSet = true;
  const result = await f.host.disable();
  assert.equal(result.state, "blocked");
  assert.equal(result.reason, "storage_unavailable");
  assert.equal(result.durable, false);
  assert.equal((await f.host.collect()).enabled, false);
  f.failSet = false;
  f.failClear = true;
  const paused = await f.host.disable();
  assert.equal(paused.enabled, false);
  assert.equal(paused.durable, true);
  assert.equal((await createCanvasHost(f.options).collect()).state, "paused");
});
test("pairing uses generated persistent device ID; bind is explicit, secrets redacted", async () => {
  const f = fixture();
  const result = await f.host.pair("C".repeat(32));
  assert.ok(!JSON.stringify(result).includes("PRIVATE"));
  const first = f.events.find((x) => Array.isArray(x));
  assert.match(first[1].devicePublicId, /^[0-9a-f-]{36}$/);
  await createCanvasHost(f.options).pair("D".repeat(32));
  const calls = f.events.filter((x) => Array.isArray(x));
  assert.equal(calls[1][1].devicePublicId, first[1].devicePublicId);
  await f.host.bind();
  assert.ok(f.events.includes("bind"));
  await f.host.enable();
  assert.equal((await f.host.pair("C".repeat(32))).reason, "pause_required");
  assert.equal((await f.host.bind()).reason, "pause_required");
});
test("corrupt preferences fail closed; invalid origins rejected", async () => {
  const f = fixture();
  await f.host.enable();
  const key = Object.keys(f.data)[0];
  f.data[key].enabled = "yes";
  assert.equal(
    (await createCanvasHost(f.options).collect()).reason,
    "host_state_invalid",
  );
  assert.throws(() =>
    createCanvasHost({
      ...f.options,
      canvasOrigin: "https://canvas.example.edu/path",
    }),
  );
});
test("control epoch is rechecked before dispatch after an awaited journal read", async () => {
  const f = fixture();
  await f.host.enable();
  let release;
  f.options.client.readDiscoveryStatus = () =>
    new Promise((r) => (release = r));
  const work = f.host.collect();
  while (!release) await new Promise((r) => setImmediate(r));
  await f.host.disable();
  await f.host.enable();
  release({ state: "active" });
  await work;
  assert.equal(f.events.includes("collect"), false);
});
test("enable is blocked during pairing so credentials cannot change under collection", async () => {
  const f = fixture();
  let release;
  f.options.client.redeem = () => new Promise((r) => (release = r));
  const pairing = f.host.pair("C".repeat(32));
  while (!release) await new Promise((r) => setImmediate(r));
  assert.equal((await f.host.enable()).reason, "identity_in_progress");
  assert.equal((await f.host.collect()).state, "busy");
  release({ state: "pending_identity" });
  await pairing;
  assert.equal((await f.host.status()).enabled, false);
});
test("production client construction is inactive; unpaired collection stops without fetching", async () => {
  const f = fixture();
  const host = createCanvasHost({ ...f.options, client: undefined });
  assert.equal((await host.reconcile()).enabled, false);
  assert.deepEqual(f.events, []);
  await host.enable();
  const result = await host.collect();
  assert.equal(result.state, "blocked");
  assert.equal(result.enabled, false);
  assert.equal(f.scheduled.size, 0);
});
test("failed enable persistence never schedules, and pairing errors never auto retry", async () => {
  const f = fixture();
  f.failSet = true;
  assert.equal((await f.host.enable()).reason, "storage_unavailable");
  assert.equal(f.scheduled.size, 0);
  f.failSet = false;
  let calls = 0;
  f.options.client.redeem = async () => {
    calls++;
    throw Error("PRIVATE CODE TOKEN");
  };
  const reply = await f.host.pair("C".repeat(32));
  assert.equal(reply.reason, "identity_failed");
  assert.ok(!JSON.stringify(reply).includes("PRIVATE"));
  await f.host.reconcile();
  await f.host.collect();
  assert.equal(calls, 1);
});
test("real collector coverage string contract preserves partial and complete status", async () => {
  for (const coverage of ["partial", "complete"]) {
    const f = fixture();
    await f.host.enable();
    f.result = { state: "finished", seen_count: 2, coverage };
    assert.equal((await f.host.collect()).coverage, coverage);
  }
});
test("rejected pairing command does not claim enabled collection has been paused", async () => {
  const f = fixture();
  await f.host.enable();
  for (const result of [
    await f.host.bind(),
    await f.host.pair("C".repeat(32)),
  ]) {
    assert.equal(result.reason, "pause_required");
    assert.notEqual(result.enabled, false);
    assert.equal((await f.host.status()).enabled, true);
  }
});
test("completed collection reports no running step while concurrent status remains accurate", async () => {
  const f = fixture();
  await f.host.enable();
  assert.equal((await f.host.collect()).running, false);
  assert.equal((await f.host.status()).running, false);
});

test("a bounded burst reuses durable steps and stops at a finished scan", async () => {
  const f = fixture();
  let calls = 0;
  f.options.client.collectDocumentPage = async () => ({
    state: ++calls === 3 ? "finished" : "progress",
    action: "document_step",
    seen_count: 2,
    coverage: "partial",
  });
  const host = createCanvasHost({ ...f.options, burstSteps: 100 });
  await host.enable();
  assert.equal((await host.collect()).state, "finished");
  assert.equal(calls, 3);
  assert.equal(f.scheduled.has(HOST_ALARMS.continuation), false);
  assert.ok(f.scheduled.has(HOST_ALARMS.periodic));
});
test("burst checks the soft time budget between steps and retains continuation", async () => {
  const f = fixture();
  let calls = 0;
  f.options.client.collectDocumentPage = async () => {
    calls++;
    f.advance(8000);
    return { state: "progress", action: "document_step" };
  };
  const host = createCanvasHost({ ...f.options, burstSteps: 100 });
  await host.enable();
  await host.collect();
  assert.equal(calls, 2);
  assert.ok(f.scheduled.has(HOST_ALARMS.continuation));
});
test("burst count is a hard cap even with an unchanged test clock", async () => {
  const f = fixture();
  let calls = 0;
  f.options.client.collectDocumentPage = async () => {
    calls++;
    return { state: "progress" };
  };
  const host = createCanvasHost({ ...f.options, burstSteps: 3 });
  await host.enable();
  await host.collect();
  assert.equal(calls, 3);
});
test("pause fences an in-flight burst and prevents the next document step", async () => {
  const f = fixture();
  let release,
    calls = 0;
  const pending = new Promise((r) => (release = r));
  f.options.client.collectDocumentPage = async () => {
    calls++;
    await pending;
    return { state: "progress" };
  };
  const host = createCanvasHost({ ...f.options, burstSteps: 100 });
  await host.enable();
  const work = host.collect();
  while (!calls) await new Promise((r) => setImmediate(r));
  assert.equal((await host.collect()).state, "busy");
  await host.disable();
  release();
  assert.equal((await work).enabled, false);
  assert.equal(calls, 1);
  assert.equal(f.scheduled.size, 0);
});
for (const burstSteps of [0, 101, 1.5, true])
  test(`reject invalid burst bound ${burstSteps}`, () => {
    const f = fixture();
    assert.throws(
      () => createCanvasHost({ ...f.options, burstSteps }),
      /invalid_configuration/,
    );
  });
