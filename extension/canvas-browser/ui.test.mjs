import { test } from "node:test";
import assert from "node:assert/strict";
import { createControls } from "./ui.mjs";

function fixture() {
  const calls = [],
    views = [];
  let clear = 0;
  let reply = { state: "paused", enabled: false, running: false };
  const controls = createControls({
    send: async (message) => {
      calls.push(message);
      return typeof reply === "function" ? reply(message) : reply;
    },
    onChange: (view) => views.push(view),
    onCodeClear: () => clear++,
  });
  return {
    controls,
    calls,
    views,
    get clear() {
      return clear;
    },
    set reply(value) {
      reply = value;
    },
  };
}
test("catalog-only completion directs the student to select scope without claiming complete content", async () => {
  const f = fixture();
  f.reply = {
    state: "awaiting_resources",
    enabled: true,
    reason: "course_selection_required",
    coverage: null,
  };
  await f.controls.refresh();
  assert.equal(f.controls.snapshot().heading, "Choose courses to collect");
  assert.match(
    f.controls.snapshot().coverage,
    /Only course discovery finished/,
  );
  assert.ok(!f.controls.snapshot().coverage.includes("complete coverage"));
});
test("refresh preserves a restarted collector's stop reason without running collection", async () => {
  const f = fixture();
  f.reply = {
    state: "blocked",
    enabled: false,
    reason: "discovery_context_changed",
  };
  await f.controls.refresh();
  assert.equal(f.controls.snapshot().heading, "Collection needs attention");
  assert.match(f.controls.snapshot().feedback, /current course selection/);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].action, "status");
});
test("only fixed diagnostic codes render, never arbitrary provider text", async () => {
  const f = fixture();
  for (const code of [
    "invalid_collection",
    "discovery_lease_expired",
    "unsafe_pagination",
  ]) {
    f.reply = { state: "blocked", enabled: false, reason: code };
    await f.controls.refresh();
    assert.ok(f.controls.snapshot().feedback.includes(code));
  }
  f.reply = {
    state: "blocked",
    enabled: false,
    reason: "PRIVATE token and course text",
  };
  await f.controls.refresh();
  assert.ok(!f.controls.snapshot().feedback.includes("PRIVATE"));
  assert.ok(f.calls.every((x) => x.action === "status"));
});
test("opening/refresh asks status only, never pairing, bind or source collection", async () => {
  const f = fixture();
  assert.deepEqual(f.calls, []);
  await f.controls.refresh();
  assert.deepEqual(f.calls, [
    { type: "wrytely.canvas.host.v1", action: "status" },
  ]);
  assert.equal(f.controls.snapshot().enabled, false);
  assert.equal(f.controls.snapshot().verified, false);
});
test("enable needs explicit identity verification and consent", async () => {
  const f = fixture();
  await f.controls.refresh();
  assert.equal(await f.controls.perform("enable", { consent: true }), false);
  f.reply = { state: "connected", enabled: false };
  await f.controls.perform("bind");
  assert.equal(f.controls.snapshot().verified, true);
  assert.equal(await f.controls.perform("enable", { consent: false }), false);
  f.reply = { state: "ready", enabled: true, running: false };
  assert.equal(await f.controls.perform("enable", { consent: true }), true);
  assert.equal(f.controls.snapshot().enabled, true);
});
test("pair validates code, clears it on dispatch and does not publish or persist it", async () => {
  const f = fixture();
  await f.controls.refresh();
  assert.equal(await f.controls.perform("pair", { code: "bad" }), false);
  assert.equal(f.calls.length, 1);
  f.reply = { state: "pending_identity", enabled: false };
  const code = "S".repeat(32);
  await f.controls.perform("pair", { code });
  assert.equal(f.clear, 1);
  assert.equal(f.calls.at(-1).code, code);
  assert.ok(!JSON.stringify(f.views).includes(code));
  assert.equal(f.controls.snapshot().verified, false);
});
test("duplicate data commands blocked; pause interrupts collect and fences its late reply", async () => {
  const f = fixture();
  f.reply = { state: "ready", enabled: true, running: false };
  await f.controls.refresh();
  let release;
  f.reply = (message) =>
    message.action === "collect"
      ? new Promise((r) => (release = r))
      : { state: "paused", enabled: false, running: true, durable: true };
  const collect = f.controls.perform("collect");
  assert.equal(await f.controls.perform("collect"), false);
  await f.controls.perform("disable");
  assert.equal(f.controls.snapshot().enabled, false);
  release({ state: "progress", enabled: true, running: false });
  await collect;
  assert.equal(f.controls.snapshot().enabled, false);
});
test("stale status reply cannot undo newer pause", async () => {
  const f = fixture();
  f.reply = { state: "ready", enabled: true };
  await f.controls.refresh();
  let release;
  f.reply = (message) =>
    message.action === "status"
      ? new Promise((r) => (release = r))
      : { state: "paused", enabled: false, durable: true };
  const read = f.controls.refresh();
  await f.controls.perform("disable");
  release({ state: "ready", enabled: true });
  await read;
  assert.equal(f.controls.snapshot().enabled, false);
});
test("unknown mutation outcomes never retry; raw replies and errors never render", async () => {
  const f = fixture();
  await f.controls.refresh();
  f.reply = () => {
    throw Error("SECRET PRIVATE SOURCE");
  };
  await f.controls.perform("pair", { code: "P".repeat(32) });
  assert.equal(f.calls.length, 2);
  assert.equal(f.controls.snapshot().uncertain, true);
  assert.ok(!JSON.stringify(f.views).includes("SECRET"));
  assert.equal(await f.controls.perform("bind"), false);
  f.reply = { state: "PRIVATE SOURCE", enabled: true, subject_id: "SECRET" };
  await f.controls.refresh();
  assert.equal(f.controls.snapshot().enabled, null);
  assert.ok(!JSON.stringify(f.views).includes("SECRET"));
});
test("failed durable pause is unknown, never shown as a saved pause", async () => {
  const f = fixture();
  f.reply = { state: "ready", enabled: true };
  await f.controls.refresh();
  f.reply = {
    state: "blocked",
    enabled: false,
    durable: false,
    reason: "storage_unavailable",
  };
  await f.controls.perform("disable");
  assert.equal(f.controls.snapshot().enabled, null);
  assert.equal(f.controls.snapshot().uncertain, true);
  assert.match(f.controls.snapshot().feedback, /not saved/i);
});
test("coverage is described as last-step partial, never as account-wide completion", async () => {
  const f = fixture();
  f.reply = {
    state: "progress",
    enabled: true,
    coverage: "partial",
    course_count: 2,
    subject_id: "SECRET",
  };
  await f.controls.refresh();
  assert.match(f.controls.snapshot().coverage, /partial/i);
  assert.ok(!JSON.stringify(f.views).includes("SECRET"));
  f.reply = { state: "ready", enabled: true, coverage: null, course_count: 0 };
  await f.controls.refresh();
  assert.match(f.controls.snapshot().coverage, /not measured/i);
});
test("dispose clears code and ignores pending replies without further messages", async () => {
  const f = fixture();
  let release;
  f.reply = () => new Promise((r) => (release = r));
  const read = f.controls.refresh();
  f.controls.dispose();
  const count = f.views.length;
  release({ state: "ready", enabled: true });
  await read;
  assert.equal(f.views.length, count);
  assert.equal(f.clear, 1);
  assert.equal(await f.controls.perform("bind"), false);
});
test("action-specific outcomes reject missing and contradictory identity/enable replies", async () => {
  for (const action of ["pair", "bind"]) {
    for (const enabled of [undefined, true, "false"]) {
      const f = fixture();
      await f.controls.refresh();
      f.reply = {
        state: action === "pair" ? "pending_identity" : "connected",
        ...(enabled === undefined ? {} : { enabled }),
      };
      assert.equal(
        await f.controls.perform(action, { code: "P".repeat(32) }),
        false,
      );
      assert.equal(f.controls.snapshot().verified, false);
      assert.equal(f.controls.snapshot().uncertain, true);
    }
  }
  for (const reply of [
    { state: "paused", enabled: false },
    { state: "busy", enabled: false, reason: "identity_in_progress" },
  ]) {
    const f = fixture();
    await f.controls.refresh();
    f.reply = { state: "connected", enabled: false };
    await f.controls.perform("bind");
    f.reply = reply;
    assert.equal(await f.controls.perform("enable", { consent: true }), false);
    assert.ok(!f.controls.snapshot().feedback.includes("Collection enabled"));
    assert.equal(f.controls.snapshot().tone, "warning");
  }
});
test("refresh replaces stale action feedback after another view changes controls", async () => {
  const f = fixture();
  f.reply = { state: "ready", enabled: true };
  await f.controls.refresh();
  f.reply = { state: "paused", enabled: false, durable: true };
  await f.controls.perform("disable");
  assert.match(f.controls.snapshot().feedback, /Pause saved/);
  f.reply = { state: "ready", enabled: true };
  await f.controls.refresh();
  assert.ok(!f.controls.snapshot().feedback.includes("No new steps"));
  assert.equal(f.controls.snapshot().tone, "info");
  f.reply = { state: "paused", enabled: false };
  await f.controls.refresh();
  f.reply = { state: "connected", enabled: false };
  await f.controls.perform("bind");
  f.reply = { state: "ready", enabled: true };
  await f.controls.perform("enable", { consent: true });
  f.reply = { state: "paused", enabled: false };
  await f.controls.refresh();
  assert.ok(!f.controls.snapshot().feedback.includes("Collection enabled"));
  assert.equal(f.controls.snapshot().enabled, false);
});
