import { test } from "node:test";
import assert from "node:assert/strict";
import { createPairingClient, PairingClientError } from "./client.mjs";

const apiOrigin = "https://agent.example.edu";
const canvasOrigin = "https://canvas.example.edu";
const code = "C".repeat(32);
const token = "T".repeat(43);
const safe = {
  connection_id: "00000000-0000-4000-8000-000000000001",
  provider: "canvas_extension",
  origin: canvasOrigin,
  state: "pending_identity",
  generation: 1,
  credential_expires_at: "2099-01-01T00:00:00+00:00",
};

function fixture(options = {}) {
  const events = [],
    calls = [],
    profiles = [],
    data = {};
  const storageArea = {
    async setAccessLevel(value) {
      events.push(["secure", value]);
    },
    async get(key) {
      events.push(["get"]);
      return structuredClone({ [key]: data[key] });
    },
    async remove(key) {
      events.push(["remove"]);
      delete data[key];
    },
    async set(value) {
      events.push(["set"]);
      Object.assign(data, structuredClone(value));
    },
  };
  const settings = {
    apiOrigin,
    canvasOrigin,
    storageArea,
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      events.push(["fetch"]);
      const response = options.api
        ? await options.api(url, init)
        : Response.json({ ...safe, ingestion_bearer: token });
      Object.defineProperty(response, "url", {
        value: url,
        configurable: true,
      });
      return response;
    },
    canvasFetch: async (url, init) => {
      profiles.push({ url, init });
      return Response.json({ id: options.subjects?.shift() ?? "7" });
    },
  };
  return {
    events,
    calls,
    profiles,
    data,
    storageArea,
    settings,
    client: createPairingClient(settings),
  };
}

const reject = (reason) => (error) =>
  error instanceof PairingClientError && error.code === reason;
const pair = (f) => f.client.redeem({ code, devicePublicId: "device-1" });

function contextReply(changes = {}) {
  return {
    ...safe,
    scope_revision: 0,
    mode: "explicit_set",
    course_ids: [],
    resource_kinds: [],
    discovery: {
      coverage: "unknown",
      last_attempt_at: null,
      last_complete_at: null,
    },
    ...changes,
  };
}

function contextFixture(reply = contextReply(), options = {}) {
  return fixture({
    api: (url, init) =>
      url.endsWith("/redeem")
        ? Response.json({ ...safe, ingestion_bearer: token })
        : options.api
          ? options.api(url, init)
          : Response.json(reply),
  });
}

test("reads current private context using the stored bearer, never returning secrets", async () => {
  const f = contextFixture({
    ...contextReply(),
    ingestion_bearer: token,
    provider_subject: "PRIVATE",
    extra: { text: "PRIVATE" },
  });
  await pair(f);
  assert.deepEqual(await f.client.readCurrentContext(), contextReply());
  const { url, init } = f.calls[1];
  assert.equal(url, `${apiOrigin}/v1/source-connections/canvas/context`);
  assert.deepEqual(JSON.parse(init.body), { origin: canvasOrigin });
  assert.equal(
    new Headers(init.headers).get("Authorization"),
    `Bearer ${token}`,
  );
  assert.equal(init.credentials, "omit");
  assert.equal(init.redirect, "error");
  assert.equal(init.cache, "no-store");
  assert.ok(init.signal instanceof AbortSignal);
  assert.equal(f.calls.length, 2);
  assert.equal(f.profiles.length, 0); // Context is not current Canvas-account verification.
});

test("accepts current scope generation and persists only the refreshed connection", async () => {
  const reply = contextReply({
    state: "connected",
    generation: 3,
    scope_revision: 2,
    mode: "all_active",
    course_ids: ["7"],
    resource_kinds: ["assignments"],
    discovery: {
      coverage: "partial",
      last_attempt_at: "2026-10-31T01:00:00Z",
      last_complete_at: null,
      private: token,
    },
  });
  const f = contextFixture(reply);
  await pair(f);
  const result = await f.client.readCurrentContext();
  assert.equal(result.generation, 3);
  assert.deepEqual(result.discovery, {
    coverage: "partial",
    last_attempt_at: "2026-10-31T01:00:00Z",
    last_complete_at: null,
  });
  assert.deepEqual(await f.client.readCachedConnection(), {
    ...safe,
    state: "connected",
    generation: 3,
  });
  assert.equal(JSON.stringify(result).includes(token), false);
  assert.equal(Object.values(f.data)[0].ingestion_bearer, token);
  assert.equal("scope_revision" in Object.values(f.data)[0].connection, false);
  result.course_ids.push("8");
  assert.deepEqual((await f.client.readCurrentContext()).course_ids, ["7"]);
});

for (const [name, changes] of Object.entries({
  "connection mismatch": {
    connection_id: "00000000-0000-4000-8000-000000000002",
  },
  "generation rollback": { generation: 0 },
  "invalid revision": { scope_revision: -1 },
  "fractional revision": { scope_revision: 0.5 },
  "invalid mode": { mode: "all_accounts" },
  "duplicate course": { course_ids: ["7", "7"] },
  "non-string course": { course_ids: [7] },
  "long course ID": { course_ids: ["1".repeat(21)] },
  "too many courses": {
    course_ids: Array.from({ length: 1001 }, (_, n) => String(n + 1)),
  },
  "unsupported kind": { resource_kinds: ["mail"] },
  "duplicate kind": { resource_kinds: ["files", "files"] },
  "invalid coverage": {
    discovery: {
      coverage: "ready",
      last_attempt_at: null,
      last_complete_at: null,
    },
  },
  "invalid timestamp": {
    discovery: {
      coverage: "partial",
      last_attempt_at: "2026-02-31T00:00:00Z",
      last_complete_at: null,
    },
  },
})) {
  test(`rejects malformed context: ${name}, retaining valid pairing`, async () => {
    const f = contextFixture(contextReply(changes));
    await pair(f);
    await assert.rejects(
      f.client.readCurrentContext(),
      reject("context_unavailable"),
    );
    assert.deepEqual(await f.client.readCachedConnection(), safe);
    assert.equal(f.calls.length, 2);
  });
}

test("rejects a positive generation rollback against the cached record", async () => {
  let reply = contextReply({ generation: 3 });
  const f = contextFixture(null, { api: () => Response.json(reply) });
  await pair(f);
  await f.client.readCurrentContext();
  reply = contextReply({ generation: 2 });
  await assert.rejects(
    f.client.readCurrentContext(),
    reject("context_unavailable"),
  );
  assert.equal((await f.client.readCachedConnection()).generation, 3);
});

test("supports the full1000-course context beyond the old16KiB lifecycle ceiling", async () => {
  const reply = contextReply({
    state: "connected",
    course_ids: Array.from({ length: 1000 }, (_, n) =>
      String(10000000000000000000n + BigInt(n)),
    ),
    resource_kinds: [
      "syllabus",
      "assignments",
      "announcements",
      "discussions",
      "modules",
      "pages",
      "files",
      "submissions",
      "grades",
    ],
  });
  assert.ok(Buffer.byteLength(JSON.stringify(reply)) > 16384);
  const f = contextFixture(reply);
  await pair(f);
  assert.deepEqual(await f.client.readCurrentContext(), reply);
});

for (const [name, api, reason] of [
  [
    "unauthorized",
    () => Response.json({ detail: "PRIVATE" }, { status: 401 }),
    "reconnect_required",
  ],
  [
    "transport",
    () => {
      throw Error("PRIVATE");
    },
    "context_unavailable",
  ],
  [
    "server",
    () => Response.json({ detail: "PRIVATE" }, { status: 503 }),
    "context_unavailable",
  ],
  [
    "malformed JSON",
    () =>
      new Response("PRIVATE", {
        headers: { "content-type": "application/json" },
      }),
    "context_unavailable",
  ],
  [
    "oversized JSON",
    () => Response.json({ ...contextReply(), noise: "x".repeat(65536) }),
    "context_unavailable",
  ],
  [
    "redirect",
    () => {
      const r = Response.json(contextReply());
      Object.defineProperty(r, "redirected", { value: true });
      return r;
    },
    "context_unavailable",
  ],
]) {
  test(`context ${name} is controlled without retry`, async () => {
    const f = contextFixture(null, { api });
    await pair(f);
    await assert.rejects(f.client.readCurrentContext(), reject(reason));
    assert.equal(f.calls.length, 2);
    assert.deepEqual(
      await f.client.readCachedConnection(),
      reason === "reconnect_required" ? null : safe,
    );
  });
}

test("missing and locally expired credentials cannot fetch context", async () => {
  const f = contextFixture();
  await assert.rejects(
    f.client.readCurrentContext(),
    reject("reconnect_required"),
  );
  assert.equal(f.calls.length, 0);
  await pair(f);
  Object.values(f.data)[0].connection.credential_expires_at =
    "2001-01-01T00:00:00Z";
  await assert.rejects(
    f.client.readCurrentContext(),
    reject("reconnect_required"),
  );
  assert.equal(f.calls.length, 1);
  assert.equal(await f.client.readCachedConnection(), null);
});

test("context storage failure does not return unpersisted state or discard pairing", async () => {
  const f = contextFixture(contextReply({ generation: 2 }));
  await pair(f);
  f.storageArea.set = async () => {
    throw Error("PRIVATE_STORAGE");
  };
  await assert.rejects(
    f.client.readCurrentContext(),
    reject("storage_unavailable"),
  );
  assert.deepEqual(await f.client.readCachedConnection(), safe);
});

test("context expiry during storage is rejected before result delivery", async () => {
  const f = contextFixture();
  await pair(f);
  const realNow = Date.now;
  const expiryAt = Date.parse(safe.credential_expires_at);
  let now = expiryAt - 1000;
  const persist = f.storageArea.set;
  f.storageArea.set = async (value) => {
    await persist(value);
    now = expiryAt;
  };
  Date.now = () => now;
  try {
    await assert.rejects(
      f.client.readCurrentContext(),
      reject("reconnect_required"),
    );
    assert.equal(await f.client.readCachedConnection(), null);
  } finally {
    Date.now = realNow;
  }
});

test("the Store's expiry-race projection triggers reconnect cleanup", async () => {
  const f = contextFixture(
    contextReply({
      state: "reconnect_required",
      credential_expires_at: "2001-01-01T00:00:00Z",
    }),
  );
  await pair(f);
  await assert.rejects(
    f.client.readCurrentContext(),
    reject("reconnect_required"),
  );
  assert.equal(await f.client.readCachedConnection(), null);
  assert.equal(f.calls.length, 2);
});

test("redeems once, secures storage before use, and never returns bearer", async () => {
  const f = fixture();
  const result = await pair(f);
  assert.deepEqual(result, safe);
  assert.equal(JSON.stringify(result).includes(token), false);
  assert.equal(f.calls.length, 1);
  assert.deepEqual(
    f.events.map((x) => x[0]),
    ["secure", "remove", "fetch", "set"],
  );
  assert.deepEqual(f.events[0][1], { accessLevel: "TRUSTED_CONTEXTS" });
  const { url, init } = f.calls[0];
  assert.equal(url, `${apiOrigin}/v1/source-connections/canvas/redeem`);
  assert.deepEqual(JSON.parse(init.body), {
    code,
    device_public_id: "device-1",
  });
  assert.equal(new Headers(init.headers).has("Authorization"), false);
  assert.equal(init.credentials, "omit");
  assert.equal(init.redirect, "error");
  assert.equal(init.cache, "no-store");
  assert.ok(init.signal instanceof AbortSignal);
  assert.equal(Object.values(f.data)[0].ingestion_bearer, token);
  assert.equal(JSON.stringify(f.data).includes(code), false);
  result.state = "disconnected";
  assert.equal(
    (await f.client.readCachedConnection()).state,
    "pending_identity",
  );
});

for (const origin of [
  "http://agent.example.edu",
  "https://agent.example.edu/",
  "https://agent.example.edu?token=x",
  "https://user:pass@agent.example.edu",
  "https://agent.example.edu:443",
]) {
  test(`rejects noncanonical config ${origin.split(":")[0]}`, () => {
    const f = fixture();
    assert.throws(
      () => createPairingClient({ ...f.settings, apiOrigin: origin }),
      reject("invalid_configuration"),
    );
  });
}

for (const input of [
  { code: "short", devicePublicId: "d" },
  { code, devicePublicId: "../other" },
  { code: 123, devicePublicId: "d" },
]) {
  test("rejects malformed pairing input before storage or network", async () => {
    const f = fixture();
    await assert.rejects(
      f.client.redeem(input),
      reject("invalid_pairing_input"),
    );
    assert.equal(f.events.length, 0);
  });
}

test("requires trusted-only storage before touching credentials", async () => {
  const f = fixture();
  f.storageArea.setAccessLevel = async () => {
    throw Error("PRIVATE_FAILURE");
  };
  await assert.rejects(pair(f), reject("storage_unavailable"));
  assert.equal(f.calls.length, 0);
  assert.deepEqual(f.data, {});
});

test("lost redemption response is unknown, clears local state and never retries", async () => {
  const f = fixture({
    api: () => {
      throw Error("PRIVATE_BODY");
    },
  });
  await assert.rejects(pair(f), reject("pairing_outcome_unknown"));
  assert.equal(f.calls.length, 1);
  assert.deepEqual(f.data, {});
});

for (const [status, reason] of [
  [400, "invalid_pairing"],
  [429, "pairing_rate_limited"],
  [503, "pairing_outcome_unknown"],
]) {
  test(`controlled redemption status ${status}`, async () => {
    const f = fixture({ api: () => new Response("PRIVATE_BODY", { status }) });
    await assert.rejects(pair(f), reject(reason));
    assert.equal(f.calls.length, 1);
    assert.deepEqual(f.data, {});
  });
}

for (const replacement of [
  { origin: "https://other.example.edu" },
  { generation: 0 },
  { ingestion_bearer: "short" },
  { state: "connected" },
  { credential_expires_at: "expired" },
  { connection_id: "not-an-id" },
  { ingestion_bearer: [token] },
  { connection_id: [safe.connection_id] },
  { credential_expires_at: "2099-02-30T00:00:00Z" },
  { credential_expires_at: "2099-01-01T00:00:00+01:60" },
]) {
  test("rejects invalid credential reply and stores nothing", async () => {
    const f = fixture({
      api: () =>
        Response.json({ ...safe, ingestion_bearer: token, ...replacement }),
    });
    await assert.rejects(pair(f), reject("pairing_outcome_unknown"));
    assert.deepEqual(f.data, {});
  });
}

test("streamed oversize success cannot persist a partial credential", async () => {
  let reads = 0,
    canceled = false;
  const f = fixture({
    api: () =>
      new Response(
        new ReadableStream({
          pull(c) {
            reads++;
            c.enqueue(new Uint8Array(9000));
          },
          cancel() {
            canceled = true;
          },
        }),
        {
          headers: {
            "Content-Type": "application/json",
            "Content-Length": "1",
          },
        },
      ),
  });
  await assert.rejects(pair(f), reject("pairing_outcome_unknown"));
  assert.equal(canceled, true);
  assert.ok(reads <= 3);
  assert.deepEqual(f.data, {});
});

test("cleanup failure quarantines recreated clients in the worker realm", async () => {
  const f = fixture();
  const set = f.storageArea.set;
  f.storageArea.set = async (value) => {
    await set(value);
    f.storageArea.remove = async () => {
      throw Error("PRIVATE_CLEANUP");
    };
    throw Error("PRIVATE_WRITE");
  };
  await assert.rejects(pair(f), reject("pairing_outcome_unknown"));
  await assert.rejects(
    f.client.readCachedConnection(),
    reject("storage_cleanup_required"),
  );
  await assert.rejects(
    createPairingClient(f.settings).bindCurrentSession(),
    reject("storage_cleanup_required"),
  );
  assert.equal(f.profiles.length, 0);
});

test("unavailable profile never substitutes an owner or sends a bind", async () => {
  const f = fixture();
  f.settings.canvasFetch = async () =>
    new Response("PRIVATE_LOGIN_HTML", {
      headers: { "Content-Type": "text/html" },
    });
  const client = createPairingClient(f.settings);
  await client.redeem({ code, devicePublicId: "d" });
  await assert.rejects(
    client.bindCurrentSession(),
    reject("canvas_session_unavailable"),
  );
  assert.equal(f.calls.length, 1);
});

for (const invalidOrigin of [
  "https://agent..example.edu",
  "https://agent.example.edu.",
]) {
  test("rejects empty or trailing host labels", () => {
    const f = fixture();
    assert.throws(
      () => createPairingClient({ ...f.settings, canvasOrigin: invalidOrigin }),
      reject("invalid_configuration"),
    );
  });
}

test("commit-then-error local write is cleaned up", async () => {
  const f = fixture();
  const set = f.storageArea.set;
  f.storageArea.set = async (value) => {
    await set(value);
    throw Error("PRIVATE_STORAGE");
  };
  await assert.rejects(pair(f), reject("pairing_outcome_unknown"));
  assert.deepEqual(f.data, {});
});

test("local cache survives a new worker client but never exposes credentials", async () => {
  const f = fixture();
  await pair(f);
  const restarted = createPairingClient(f.settings);
  assert.deepEqual(await restarted.readCachedConnection(), safe);
  assert.equal(f.calls.length, 1);
});

test("bind derives current profile, sends only ingestion auth and rechecks identity", async () => {
  const f = fixture({
    api: (_url, init) =>
      Response.json(
        init.headers.Authorization
          ? { ...safe, state: "connected" }
          : { ...safe, ingestion_bearer: token },
      ),
  });
  await pair(f);
  const result = await f.client.bindCurrentSession();
  assert.equal(result.state, "connected");
  assert.equal(f.profiles.length, 2);
  for (const p of f.profiles) {
    assert.equal(p.url, `${canvasOrigin}/api/v1/users/self/profile`);
    assert.equal(p.init.credentials, "include");
  }
  assert.equal(f.calls[1].init.headers.Authorization, `Bearer ${token}`);
  assert.deepEqual(JSON.parse(f.calls[1].init.body), {
    origin: canvasOrigin,
    provider_subject: "7",
  });
  assert.equal(JSON.stringify(result).includes(token), false);
});

test("revoked credential clears local cache", async () => {
  const f = fixture({
    api: (url) =>
      url.endsWith("/bind")
        ? new Response("PRIVATE_BODY", { status: 401 })
        : Response.json({ ...safe, ingestion_bearer: token }),
  });
  await pair(f);
  await assert.rejects(
    f.client.bindCurrentSession(),
    reject("reconnect_required"),
  );
  assert.deepEqual(f.data, {});
});

test("account change between profile checks attempts server fence then clears local state", async () => {
  const f = fixture({
    subjects: ["7", "8"],
    api: (url, init) => {
      if (url.endsWith("/redeem"))
        return Response.json({ ...safe, ingestion_bearer: token });
      return JSON.parse(init.body).provider_subject === "7"
        ? Response.json({ ...safe, state: "connected" })
        : new Response("", { status: 401 });
    },
  });
  await pair(f);
  await assert.rejects(
    f.client.bindCurrentSession(),
    reject("canvas_account_changed"),
  );
  assert.equal(f.calls.length, 3);
  assert.equal(JSON.parse(f.calls[2].init.body).provider_subject, "8");
  assert.deepEqual(f.data, {});
});

test("expired local credentials never reach a provider", async () => {
  const f = fixture();
  await pair(f);
  Object.values(f.data)[0].connection.credential_expires_at =
    "2000-01-01T00:00:00Z";
  assert.equal(
    (await f.client.readCachedConnection()).state,
    "reconnect_required",
  );
  await assert.rejects(
    f.client.bindCurrentSession(),
    reject("reconnect_required"),
  );
  assert.equal(f.profiles.length, 0);
});

test("two clients in one worker cannot concurrently mutate the same storage area", async () => {
  let finish;
  const f = fixture({
    api: () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  });
  const pending = pair(f);
  await new Promise((resolve) => setImmediate(resolve));
  const other = createPairingClient(f.settings);
  await assert.rejects(
    other.redeem({ code, devicePublicId: "d" }),
    reject("operation_in_progress"),
  );
  finish(Response.json({ ...safe, ingestion_bearer: token }));
  await pending;
});

test("successful C1 bind cannot silently adopt a higher credential generation", async () => {
  const f = fixture({
    api: (url) =>
      Response.json(
        url.endsWith("/redeem")
          ? { ...safe, ingestion_bearer: token }
          : { ...safe, state: "connected", generation: 2 },
      ),
  });
  await pair(f);
  await assert.rejects(
    f.client.bindCurrentSession(),
    reject("binding_outcome_unknown"),
  );
  assert.deepEqual(f.data, {});
});

test("response extras and source fields never become local records", async () => {
  const f = fixture({
    api: () =>
      Response.json({
        ...safe,
        ingestion_bearer: token,
        extra: "PRIVATE_EXTRA",
      }),
  });
  assert.deepEqual(await pair(f), safe);
  assert.equal(JSON.stringify(f.data).includes("PRIVATE_EXTRA"), false);
});

test("identity recheck failure after bind clears the uncertain local result", async () => {
  const f = fixture({
    api: (url) =>
      Response.json(
        url.endsWith("/redeem")
          ? { ...safe, ingestion_bearer: token }
          : { ...safe, state: "connected" },
      ),
  });
  let count = 0;
  const client = createPairingClient({
    ...f.settings,
    canvasFetch: async () =>
      ++count === 1
        ? Response.json({ id: "7" })
        : new Response("PRIVATE_LOGIN", { status: 401 }),
  });
  await client.redeem({ code, devicePublicId: "d" });
  await assert.rejects(
    client.bindCurrentSession(),
    reject("binding_outcome_unknown"),
  );
  assert.deepEqual(f.data, {});
});

test("null pairing input is a controlled failure before any access", async () => {
  const f = fixture();
  await assert.rejects(f.client.redeem(null), reject("invalid_pairing_input"));
  assert.equal(f.events.length, 0);
});

test("successful C1 bind cannot roll back the cached generation", async () => {
  const f = fixture({
    api: (url) =>
      Response.json(
        url.endsWith("/redeem")
          ? { ...safe, generation: 2, ingestion_bearer: token }
          : { ...safe, state: "connected" },
      ),
  });
  await pair(f);
  await assert.rejects(
    f.client.bindCurrentSession(),
    reject("binding_outcome_unknown"),
  );
  assert.deepEqual(f.data, {});
});
