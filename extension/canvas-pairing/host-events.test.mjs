import { test } from "node:test";
import assert from "node:assert/strict";
import { registerCanvasHost, HOST_MESSAGE } from "./host-events.mjs";
import { HOST_ALARMS } from "./host.mjs";

function event() {
  const listeners = new Set();
  return {
    listeners,
    addListener: (fn) => listeners.add(fn),
    removeListener: (fn) => listeners.delete(fn),
  };
}
function fixture() {
  const calls = [];
  const chrome = {
    runtime: {
      id: "trusted",
      getURL: (path) => `chrome-extension://trusted/${path}`,
      onMessage: event(),
      onStartup: event(),
      onInstalled: event(),
    },
    alarms: { onAlarm: event() },
    storage: { local: {} },
  };
  const host = Object.fromEntries(
    ["status", "enable", "disable", "collect", "reconcile", "pair", "bind"].map(
      (name) => [
        name,
        async (arg) => {
          calls.push([name, arg]);
          return { state: name };
        },
      ],
    ),
  );
  const options = {
    chrome,
    apiOrigin: "https://agent.example.edu",
    canvasOrigin: "https://canvas.example.edu",
    host,
  };
  const sender = { id: "trusted", url: chrome.runtime.getURL("popup.html") };
  const send = (message, from = sender) =>
    new Promise((resolve) => {
      const listener = [...chrome.runtime.onMessage.listeners][0];
      const keep = listener(message, from, (value) =>
        resolve({ keep: true, value }),
      );
      if (keep !== true) resolve({ keep: false });
    });
  return { chrome, host, options, calls, sender, send };
}
test("register once synchronously, restore via ready/startup, dispose permits worker recreation", async () => {
  const f = fixture(),
    registration = registerCanvasHost(f.options);
  assert.equal(f.chrome.runtime.onMessage.listeners.size, 1);
  assert.equal(registerCanvasHost(f.options), registration);
  await registration.ready;
  assert.equal(f.calls.length, 1);
  for (const fn of f.chrome.runtime.onStartup.listeners) await fn();
  assert.equal(f.calls.length, 2);
  assert.throws(() =>
    registerCanvasHost({
      ...f.options,
      canvasOrigin: "https://other.example.edu",
    }),
  );
  registration.dispose();
  assert.equal(f.chrome.runtime.onMessage.listeners.size, 0);
  await registerCanvasHost(f.options).ready;
  assert.equal(f.chrome.runtime.onMessage.listeners.size, 1);
});
test("only exact popup/options same extension senders can invoke commands", async () => {
  const f = fixture();
  await registerCanvasHost(f.options).ready;
  f.calls.length = 0;
  for (const sender of [
    undefined,
    {},
    { ...f.sender, id: "foreign" },
    { ...f.sender, tab: { id: 1 } },
    { ...f.sender, url: "https://canvas.example.edu" },
    { ...f.sender, url: f.sender.url + "?x=1" },
    { ...f.sender, url: f.sender.url + "#x" },
    { ...f.sender, url: "chrome-extension://trusted/worker.mjs" },
  ]) {
    assert.equal(
      (await f.send({ type: HOST_MESSAGE, action: "enable" }, sender ?? null))
        .keep,
      false,
    );
  }
  assert.equal(f.calls.length, 0);
  assert.equal(
    (await f.send({ type: HOST_MESSAGE, action: "enable" })).value.state,
    "enable",
  );
  assert.equal(
    (
      await f.send(
        { type: HOST_MESSAGE, action: "status" },
        { ...f.sender, url: f.chrome.runtime.getURL("options.html") },
      )
    ).value.state,
    "status",
  );
});
test("strict command shape rejects unknown keys, owner ids, force and malformed pairing codes", async () => {
  const f = fixture();
  await registerCanvasHost(f.options).ready;
  f.calls.length = 0;
  for (const message of [
    null,
    [],
    { action: "enable" },
    { type: HOST_MESSAGE, action: "other" },
    { type: HOST_MESSAGE, action: "collect", force: true },
    { type: HOST_MESSAGE, action: "enable", owner_id: "7" },
    { type: HOST_MESSAGE, action: "pair" },
    { type: HOST_MESSAGE, action: "pair", code: "x" },
    { type: HOST_MESSAGE, action: "status", code: "C".repeat(32) },
  ])
    assert.equal((await f.send(message)).keep, false);
  assert.equal(f.calls.length, 0);
  await f.send({ type: HOST_MESSAGE, action: "pair", code: "C".repeat(32) });
  assert.deepEqual(f.calls, [["pair", "C".repeat(32)]]);
});
test("only own alarm names collect; unrelated events remain untouched", async () => {
  const f = fixture();
  await registerCanvasHost(f.options).ready;
  f.calls.length = 0;
  const listener = [...f.chrome.alarms.onAlarm.listeners][0];
  await listener({ name: "unrelated" });
  assert.equal(f.calls.length, 0);
  await listener({ name: HOST_ALARMS.periodic });
  await listener({ name: HOST_ALARMS.continuation });
  assert.deepEqual(
    f.calls.map((x) => x[0]),
    ["collect", "collect"],
  );
});
test("async errors and closed popup are caught without exposing error messages", async () => {
  const f = fixture();
  f.host.collect = async () => {
    throw Error("PRIVATE");
  };
  await registerCanvasHost(f.options).ready;
  const result = await f.send({ type: HOST_MESSAGE, action: "collect" });
  assert.equal(result.keep, true);
  assert.equal(result.value.reason, "host_failed");
  assert.ok(!JSON.stringify(result).includes("PRIVATE"));
  const listener = [...f.chrome.runtime.onMessage.listeners][0];
  assert.equal(
    listener({ type: HOST_MESSAGE, action: "status" }, f.sender, () => {
      throw Error("closed");
    }),
    true,
  );
  await new Promise((r) => setImmediate(r));
});

test("full own options tab can read status and pause using Chrome top-level sender metadata", async () => {
  const f = fixture();
  await registerCanvasHost(f.options).ready;
  f.calls.length = 0;
  const sender = {
    id: f.chrome.runtime.id,
    url: f.chrome.runtime.getURL("options.html"),
    origin: "chrome-extension://trusted",
    frameId: 0,
    tab: { id: 42 },
  };
  for (const action of ["status", "disable"])
    assert.equal(
      (await f.send({ type: HOST_MESSAGE, action }, sender)).keep,
      true,
    );
  assert.deepEqual(
    f.calls.map((x) => x[0]),
    ["status", "disable"],
  );
});
test("tab metadata never permits web content, frames, another extension, or mismatched options pages", async () => {
  const f = fixture();
  await registerCanvasHost(f.options).ready;
  f.calls.length = 0;
  const sender = {
    id: f.chrome.runtime.id,
    url: f.chrome.runtime.getURL("options.html"),
    origin: "chrome-extension://trusted",
    frameId: 0,
    tab: { id: 42 },
  };
  for (const value of [
    { ...sender, url: "https://canvas.example.edu/" },
    { ...sender, id: "other" },
    { ...sender, origin: "https://canvas.example.edu" },
    { ...sender, frameId: 1 },
    { ...sender, frameId: undefined },
    { ...sender, tab: { id: 42, url: "https://canvas.example.edu/" } },
    { ...sender, tab: { id: -1 } },
    { ...sender, tab: { id: "42" } },
    { ...sender, tab: null },
    { ...sender, url: f.chrome.runtime.getURL("popup.html") },
  ])
    assert.equal(
      (await f.send({ type: HOST_MESSAGE, action: "enable" }, value)).keep,
      false,
    );
  assert.equal(f.calls.length, 0);
});
