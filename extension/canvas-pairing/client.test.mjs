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
