import { test } from "node:test";
import assert from "node:assert/strict";
import { createPairingClient, PairingClientError } from "./client.mjs";

const apiOrigin = "https://agent.example.edu",
  canvasOrigin = "https://canvas.example.edu";
const token = "T".repeat(43);
const id = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const expires = "2099-01-01T00:00:00Z";
const key = `wrytely.canvas.connection.v1:${apiOrigin}:${canvasOrigin}`;
const safe = {
  connection_id: id(1),
  provider: "canvas_extension",
  origin: canvasOrigin,
  state: "connected",
  generation: 1,
  credential_expires_at: expires,
};
const error = (code) => (e) =>
  e instanceof PairingClientError && e.code === code;
const page = (cursor = null) => ({
  observed_at: "2026-10-31T00:00:00Z",
  next_cursor: cursor,
  coverage: {
    state: cursor ? "partial" : "complete",
    reason: cursor ? "more_pages" : null,
  },
  items: [
    {
      provider_id: "101",
      provider_updated_at: null,
      title: "Synthetic course",
      reference: `${canvasOrigin}/courses/101`,
      content: "",
      fields: {
        course_code: "SYN-101",
        timezone: "America/Denver",
        enrollment_state: "active",
      },
      coverage: "complete",
      missing: [],
    },
  ],
});

function fixture() {
  const data = {
    [key]: {
      schema_version: 1,
      api_origin: apiOrigin,
      connection: safe,
      ingestion_bearer: token,
    },
  };
  const f = {
    data,
    calls: [],
    events: [],
    applied: 0,
    leases: 1,
    receipts: new Map(),
    context: {
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
    },
    checkpoint: {
      resource: "courses",
      sequence: 0,
      next_cursor: null,
      scope_revision: 0,
    },
    profiles: [],
    loss: null,
    override: null,
    storageFailure: null,
    unauthorized: false,
  };
  f.storageArea = {
    async setAccessLevel(value) {
      assert.deepEqual(value, { accessLevel: "TRUSTED_CONTEXTS" });
    },
    async get(name) {
      return structuredClone({ [name]: data[name] });
    },
    async remove(name) {
      delete data[name];
    },
    async set(value) {
      const state = value[key]?.discovery;
      f.events.push({
        type: "persist",
        pending: state?.pending?.operation ?? null,
      });
      if (f.storageFailure?.(state, "before")) throw Error("PRIVATE_STORAGE");
      Object.assign(data, structuredClone(value));
      if (f.storageFailure?.(state, "after")) throw Error("PRIVATE_STORAGE");
    },
  };
  const json = (body, url, status = 200) => {
    const response = Response.json(body, { status });
    Object.defineProperty(response, "url", { value: url });
    return response;
  };
  f.fetch = async (url, init) => {
    const action = url.split("/canvas/")[1],
      body = JSON.parse(init.body);
    f.calls.push({ action, body: structuredClone(body), init });
    if (action === "context") return json(f.context, url);
    if (action === "redeem") {
      f.context = { ...f.context, generation: 2, state: "pending_identity" };
      return json({ ...f.context, ingestion_bearer: "R".repeat(43) }, url);
    }
    if (action === "bind")
      return json({ detail: "Reconnect Canvas" }, url, 401);
    assert.equal(
      new Headers(init.headers).get("authorization"),
      `Bearer ${token}`,
    );
    assert.equal(init.credentials, "omit");
    assert.equal(init.redirect, "error");
    assert.equal(init.cache, "no-store");
    f.events.push({ type: "send", operation: action.split("/")[1] });
    if (f.onSend) await f.onSend(action, body);
    if (f.unauthorized) return json({ detail: "Reconnect Canvas" }, url, 401);
    if (f.loss === "before") {
      f.loss = null;
      throw Error("PRIVATE_NETWORK");
    }
    const operation = action.split("/")[1];
    if (operation === "resume" && f.resumeError)
      return json({ detail: { code: f.resumeError } }, url, 409);
    const requestKey =
      body.begin_key ?? body.resume_key ?? body.batch_key ?? body.finish_key;
    const receiptKey = `${operation}:${requestKey}`;
    let result = f.receipts.get(receiptKey);
    if (result)
      result = {
        ...structuredClone(result),
        ...(operation === "begin" ? {} : { replayed: true }),
      };
    else {
      if (
        ["batch", "resource", "finish"].includes(operation) &&
        body.lease_token !== id(f.leases + 10)
      )
        return json({ detail: { code: "lease_replaced" } }, url, 409);
      if (operation === "begin" || operation === "resume") {
        if (operation === "begin")
          f.resources = [
            { resource_key: "courses", coverage: "open", reason: null },
            ...f.context.course_ids.flatMap((course) =>
              f.context.resource_kinds.map((kind) => ({
                resource_key: `${course}/${kind}`,
                coverage: "open",
                reason: null,
              })),
            ),
          ];
        if (operation === "resume") f.leases++;
        result = {
          scan_id: id(2),
          scan_sequence: 1,
          lease_token: id(f.leases + 10),
          lease_expires_at: expires,
          checkpoint: structuredClone(f.checkpoint),
        };
      } else if (operation === "batch") {
        if (
          JSON.stringify(body.expected_checkpoint) !==
          JSON.stringify(f.checkpoint)
        )
          return json({ detail: { code: "checkpoint_changed" } }, url, 409);
        f.applied++;
        if (f.context.mode === "all_active")
          for (const item of body.envelope.items) {
            if (item.fields.enrollment_state === "active") {
              if (!f.context.course_ids.includes(item.provider_id))
                f.context.course_ids.push(item.provider_id);
              for (const kind of f.context.resource_kinds)
                if (
                  !f.resources.some(
                    (r) => r.resource_key === `${item.provider_id}/${kind}`,
                  )
                )
                  f.resources.push({
                    resource_key: `${item.provider_id}/${kind}`,
                    coverage: "open",
                    reason: null,
                  });
            } else
              f.context.course_ids = f.context.course_ids.filter(
                (id) => id !== item.provider_id,
              );
          }
        f.checkpoint = {
          ...f.checkpoint,
          sequence: f.checkpoint.sequence + 1,
          next_cursor: body.envelope.next_cursor,
        };
        result = {
          receipt_id: id(30 + f.applied),
          scan_id: id(2),
          batch_key: body.batch_key,
          batch_digest: "a".repeat(64),
          source_versions: [],
          checkpoint: structuredClone(f.checkpoint),
          coverage: body.envelope.coverage.state,
          replayed: false,
        };
      } else if (operation === "resource") {
        const row = f.resources.find(
          (r) => r.resource_key === body.resource_key,
        );
        if (!row)
          return json({ detail: { code: "resource_not_selected" } }, url, 409);
        row.coverage = body.outcome;
        row.reason = body.reason;
        result = {
          receipt_id: id(80),
          resource_key: body.resource_key,
          coverage: body.outcome,
          reason: body.reason,
          seen_count: f.applied,
          finished_at: expires,
          checkpoint: structuredClone(f.checkpoint),
          source_manifest_digest: null,
          replayed: false,
        };
      } else {
        if (f.resources.some((r) => r.coverage === "open"))
          return json({ detail: { code: "resources_open" } }, url, 409);
        result = {
          scan_id: id(2),
          coverage:
            f.finishCoverage ??
            (f.resources.every((r) => r.coverage === "complete")
              ? "complete"
              : "partial"),
          resources: f.resources ?? [
            { resource_key: "courses", coverage: "complete", reason: null },
          ],
          replayed: false,
        };
      }
      f.receipts.set(receiptKey, structuredClone(result));
    }
    if (f.loss === "after") {
      f.loss = null;
      throw Error("PRIVATE_NETWORK");
    }
    if (f.override) result = f.override(operation, structuredClone(result));
    return json(result, url);
  };
  f.client = () =>
    createPairingClient({
      apiOrigin,
      canvasOrigin,
      storageArea: f.storageArea,
      fetchImpl: f.fetch,
      canvasFetch: async () => {
        if (f.onProfile) await f.onProfile();
        return Response.json({ id: f.profiles.shift() ?? "7" });
      },
    });
  f.rpc = () => f.calls.filter((c) => c.action.startsWith("discovery/"));
  return f;
}

test("persists begin before dispatch and hides private lease from results/status", async () => {
  const f = fixture(),
    client = f.client();
  f.onSend = () =>
    assert.equal(f.data[key].discovery.pending.operation, "begin");
  const result = await client.beginDiscovery();
  assert.equal(result.checkpoint.sequence, 0);
  assert.equal(f.data[key].discovery.pending, null);
  assert.equal(f.rpc().length, 1);
  assert.equal(JSON.stringify(result).includes(token), false);
  assert.equal(JSON.stringify(result).includes(id(11)), false);
  const status = await client.readDiscoveryStatus();
  assert.equal(status.state, "active");
  assert.equal(JSON.stringify(status).includes("lease_token"), false);
});

test("restart replays an unknown committed page without new capture or duplicate application", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.loss = "after";
  await assert.rejects(
    client.commitDiscoveryPage(page("PRIVATE_CURSOR")),
    error("discovery_outcome_unknown"),
  );
  const original = structuredClone(f.data[key].discovery.pending.body);
  assert.equal(f.applied, 1);
  const result = await f.client().retryDiscovery();
  assert.equal(result.checkpoint.sequence, 1);
  assert.equal(result.seen_count, 1);
  assert.equal(f.applied, 1);
  assert.deepEqual(
    f
      .rpc()
      .filter((c) => c.action.endsWith("/batch"))
      .map((c) => c.body),
    [original, original],
  );
  assert.equal(
    JSON.stringify(await f.client().readDiscoveryStatus()).includes(
      "PRIVATE_CURSOR",
    ),
    false,
  );
});

test("pending begin survives restart and recovers its original request key", async () => {
  const f = fixture();
  f.loss = "after";
  await assert.rejects(
    f.client().beginDiscovery(),
    error("discovery_outcome_unknown"),
  );
  const body = structuredClone(f.data[key].discovery.pending.body);
  await f.client().retryDiscovery();
  assert.deepEqual(
    f.rpc().map((c) => c.body),
    [body, body],
  );
});

test("resume journals its own key and retains an unacknowledged page", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.loss = "before";
  await assert.rejects(
    client.commitDiscoveryPage(page()),
    error("discovery_outcome_unknown"),
  );
  const capture = structuredClone(f.data[key].discovery.pending.body.envelope);
  f.leases++;
  await assert.rejects(
    client.retryDiscovery(),
    error("discovery_lease_replaced"),
  );
  f.loss = "after";
  await assert.rejects(
    client.resumeDiscovery(),
    error("discovery_outcome_unknown"),
  );
  await f.client().resumeDiscovery();
  assert.deepEqual(
    f
      .rpc()
      .filter((c) => c.action.endsWith("/resume"))
      .map((c) => c.body.resume_key),
    [f.rpc().find((c) => c.action.endsWith("/resume")).body.resume_key].flatMap(
      (x) => [x, x],
    ),
  );
  assert.deepEqual(f.data[key].discovery.pending.body.envelope, capture);
  await client.retryDiscovery();
  assert.equal(f.applied, 1);
});

test("resume can reconcile a page committed before its response was lost", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.loss = "after";
  await assert.rejects(
    client.commitDiscoveryPage(page()),
    error("discovery_outcome_unknown"),
  );
  await client.resumeDiscovery();
  assert.equal((await client.retryDiscovery()).seen_count, 1);
  assert.equal(f.applied, 1);
});

test("pending capture cannot be overwritten by another page or close", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.loss = "after";
  await assert.rejects(
    client.commitDiscoveryPage(page()),
    error("discovery_outcome_unknown"),
  );
  await assert.rejects(
    client.commitDiscoveryPage(page()),
    error("discovery_pending_operation"),
  );
  await assert.rejects(
    client.finishDiscovery(),
    error("discovery_pending_operation"),
  );
  assert.equal(f.rpc().length, 2);
});

test("storage failure before dispatch never sends an unpersisted intent", async () => {
  const f = fixture();
  f.storageFailure = (state, when) => !!state?.pending && when === "before";
  await assert.rejects(
    f.client().beginDiscovery(),
    error("storage_unavailable"),
  );
  assert.equal(f.rpc().length, 0);
});

test("ack storage failure preserves exact retryable intent", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.storageFailure = (state, when) =>
    !!state && !state.pending && state.seen_count === 1 && when === "before";
  await assert.rejects(
    client.commitDiscoveryPage(page()),
    error("storage_unavailable"),
  );
  assert.ok(f.data[key].discovery.pending);
  f.storageFailure = null;
  await f.client().retryDiscovery();
  assert.equal(f.applied, 1);
});

for (const change of ["generation", "scope", "account", "credential"]) {
  test(`pending replay is fenced after ${change} changes`, async () => {
    const f = fixture(),
      client = f.client();
    await client.beginDiscovery();
    f.loss = "before";
    await assert.rejects(
      client.commitDiscoveryPage(page()),
      error("discovery_outcome_unknown"),
    );
    if (change === "generation") f.context.generation++;
    if (change === "scope") f.context.scope_revision++;
    if (change === "account") f.profiles.push("8");
    if (change === "credential") f.unauthorized = true;
    const reason =
      change === "account"
        ? "canvas_account_changed"
        : change === "credential"
          ? "reconnect_required"
          : "discovery_context_changed";
    await assert.rejects(client.retryDiscovery(), error(reason));
    if (["generation", "scope", "account"].includes(change))
      assert.equal(f.rpc().length, 2);
  });
}

test("malformed receipt retains pending intent and never advances checkpoint", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.override = (op, result) =>
    op === "batch"
      ? { ...result, checkpoint: { ...result.checkpoint, sequence: 99 } }
      : result;
  await assert.rejects(
    client.commitDiscoveryPage(page()),
    error("discovery_outcome_unknown"),
  );
  assert.equal(f.data[key].discovery.scan.checkpoint.sequence, 0);
  f.override = null;
  await client.retryDiscovery();
  assert.equal(f.applied, 1);
});

test("unexpected remote progress stops rather than guessing cumulative counts", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.checkpoint.sequence = 3;
  await assert.rejects(
    client.resumeDiscovery(),
    error("discovery_reconciliation_required"),
  );
});

test("metadata only, exact capture bounds and no academic completion", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  await assert.rejects(
    client.commitDiscoveryPage({
      ...page(),
      items: Array(51).fill(page().items[0]),
    }),
    error("invalid_discovery_input"),
  );
  const academic = page();
  academic.items[0].content = "PRIVATE_RAW_TEXT";
  await assert.rejects(
    client.commitDiscoveryPage(academic),
    error("invalid_discovery_input"),
  );
  await assert.rejects(
    client.finishDiscoveryResource({
      resource_key: "101/assignments",
      outcome: "complete",
      reason: null,
    }),
    error("invalid_discovery_input"),
  );
  assert.equal(f.rpc().length, 1);
});

test("finished aggregate remains partial and allows the next scan", async () => {
  const f = fixture(),
    client = f.client();
  f.context.course_ids = ["101"];
  f.context.resource_kinds = ["assignments"];
  await client.beginDiscovery();
  await client.commitDiscoveryPage(page());
  await client.finishDiscoveryResource({
    resource_key: "courses",
    outcome: "complete",
    reason: null,
  });
  await client.finishDiscoveryResource({
    resource_key: "101/assignments",
    outcome: "unsupported",
    reason: "unsupported_format",
  });
  const result = await client.finishDiscovery();
  assert.equal(result.coverage, "partial");
  assert.equal((await client.readDiscoveryStatus()).state, "finished");
  f.checkpoint = {
    resource: "courses",
    sequence: 0,
    next_cursor: null,
    scope_revision: 0,
  };
  await client.beginDiscovery();
});

test("credential cleanup clears pending journal in the same storage namespace", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.context.state = "reconnect_required";
  await assert.rejects(client.resumeDiscovery(), error("reconnect_required"));
  assert.deepEqual(f.data, {});
});

test("successful re-pair replaces the credential and removes the old journal atomically", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  await client.redeem({ code: "C".repeat(32), devicePublicId: "device-1" });
  assert.equal((await client.readDiscoveryStatus()).state, "idle");
  assert.equal(f.data[key].ingestion_bearer, "R".repeat(43));
  assert.equal("discovery" in f.data[key], false);
  assert.equal(Object.keys(f.data).length, 1);
});

test("a definitively rejected resume cannot block replay of an already committed finish", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  await client.commitDiscoveryPage(page());
  await client.finishDiscoveryResource({
    resource_key: "courses",
    outcome: "complete",
    reason: null,
  });
  f.loss = "after";
  await assert.rejects(
    client.finishDiscovery(),
    error("discovery_outcome_unknown"),
  );
  f.resumeError = "scan_terminal";
  await assert.rejects(
    client.resumeDiscovery(),
    error("discovery_scan_terminal"),
  );
  assert.equal((await client.retryDiscovery()).state, "finished");
});

for (const change of ["account", "generation"]) {
  test(`control change during backend operation prevents result delivery: ${change}`, async () => {
    const f = fixture(),
      client = f.client();
    if (change === "account") f.profiles.push("7", "8");
    else
      f.onSend = () => {
        f.context.generation = 2;
      };
    await assert.rejects(
      client.beginDiscovery(),
      error(
        change === "account"
          ? "canvas_account_changed"
          : "discovery_context_changed",
      ),
    );
    if (change === "account") assert.deepEqual(f.data, {});
    else assert.equal((await client.readDiscoveryStatus()).state, "blocked");
  });
}

test("full5000-record/100-page limit is supported and the next page is rejected", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  for (let n = 0; n < 100; n++) {
    const value = page(n < 99 ? `cursor-${n}` : null);
    value.items = Array.from({ length: 50 }, (_, offset) => {
      const provider_id = String(n * 50 + offset + 1);
      return {
        ...page().items[0],
        provider_id,
        reference: `${canvasOrigin}/courses/${provider_id}`,
      };
    });
    const result = await client.commitDiscoveryPage(value);
    assert.equal(result.seen_count, (n + 1) * 50);
  }
  await assert.rejects(
    client.commitDiscoveryPage(page()),
    error("invalid_discovery_input"),
  );
  assert.equal(f.applied, 100);
});

test("maximum aggregate decoding uses a synthetic previously acknowledged resource ledger", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  await client.commitDiscoveryPage(page());
  await client.finishDiscoveryResource({
    resource_key: "courses",
    outcome: "complete",
    reason: null,
  });
  const kinds = [
    "syllabus",
    "assignments",
    "announcements",
    "discussions",
    "modules",
    "pages",
    "files",
    "submissions",
    "grades",
  ];
  f.resources = [
    { resource_key: "courses", coverage: "complete", reason: null },
    ...Array.from({ length: 6000 }, (_, n) =>
      kinds.map((kind) => ({
        resource_key: `${10000000000000000000n + BigInt(n)}/${kind}`,
        coverage: "unsupported",
        reason: "unsupported_format",
      })),
    ).flat(),
  ];
  f.finishCoverage = "partial";
  // Capacity fixture only: represents previously acknowledged rows, not a6000-course live run.
  f.data[key].discovery.required = f.resources.map((r) => r.resource_key);
  f.data[key].discovery.closed = [...f.data[key].discovery.required];
  f.data[key].discovery.incomplete_resource = true;
  assert.ok(Buffer.byteLength(JSON.stringify(f.resources)) > 65536);
  assert.ok(Buffer.byteLength(JSON.stringify(f.resources)) < 8 * 1024 * 1024);
  const result = await client.finishDiscovery();
  assert.equal(result.coverage, "partial");
  assert.equal("resources" in result, false);
  assert.equal(f.data[key].discovery.finished.resource_count, 54001);
});

test("oversized reply keeps exact pending intent for explicit retry", async () => {
  const f = fixture(),
    client = f.client();
  f.override = (_, result) => ({
    ...result,
    private: "x".repeat(2 * 1024 * 1024),
  });
  await assert.rejects(
    client.beginDiscovery(),
    error("discovery_outcome_unknown"),
  );
  assert.equal(f.rpc().length, 1);
  assert.equal(f.data[key].discovery.pending.operation, "begin");
  f.override = null;
  await client.retryDiscovery();
});

test("invalid stored journal fails closed while retaining valid pairing", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.data[key].discovery.version = 99;
  await assert.rejects(
    client.readDiscoveryStatus(),
    error("discovery_journal_invalid"),
  );
  assert.deepEqual(await client.readCachedConnection(), safe);
});

for (const text of ["\ud800", "PRIVATE\u0000TEXT"]) {
  test("nonportable source Unicode is rejected before creating an intent", async () => {
    const f = fixture(),
      client = f.client();
    await client.beginDiscovery();
    const value = page();
    value.items[0].title = text;
    await assert.rejects(
      client.commitDiscoveryPage(value),
      error("invalid_discovery_input"),
    );
    assert.equal(f.rpc().length, 1);
    assert.equal(f.data[key].discovery.pending, null);
  });
}

test("valid4000-codepoint cursor survives restart without a UTF16 length restriction", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  const value = "🧪".repeat(4000);
  await client.commitDiscoveryPage(page(value));
  assert.equal(
    (await f.client().resumeDiscovery()).checkpoint.next_cursor,
    value,
  );
});

test("persist failure after saving intent still permits exact explicit recovery", async () => {
  const f = fixture(),
    client = f.client();
  f.storageFailure = (state, when) => !!state?.pending && when === "after";
  await assert.rejects(client.beginDiscovery(), error("storage_unavailable"));
  assert.equal(f.rpc().length, 0);
  f.storageFailure = null;
  await client.retryDiscovery();
  assert.equal(f.rpc().length, 1);
});

test("an acknowledgement saved before a storage error resumes without resubmitting its page", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.storageFailure = (state, when) =>
    !!state && !state.pending && state.seen_count === 1 && when === "after";
  await assert.rejects(
    client.commitDiscoveryPage(page()),
    error("storage_unavailable"),
  );
  f.storageFailure = null;
  const result = await f.client().resumeDiscovery();
  assert.equal(result.seen_count, 1);
  assert.equal(f.applied, 1);
});

test("pairing and discovery operations share the same per-storage operation lock", async () => {
  const f = fixture(),
    client = f.client();
  let entered, release;
  const started = new Promise((resolve) => {
    entered = resolve;
  });
  const wait = new Promise((resolve) => {
    release = resolve;
  });
  f.onSend = async () => {
    entered();
    await wait;
  };
  const operation = client.beginDiscovery();
  await started;
  await assert.rejects(
    client.readCurrentContext(),
    error("operation_in_progress"),
  );
  await assert.rejects(
    f.client().beginDiscovery(),
    error("operation_in_progress"),
  );
  release();
  await operation;
});

test("expired local lease blocks a new page until explicit resume", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.data[key].discovery.scan.lease_expires_at = "2001-01-01T00:00:00Z";
  await assert.rejects(
    client.commitDiscoveryPage(page()),
    error("discovery_lease_expired"),
  );
  assert.equal(f.rpc().length, 1);
  await client.resumeDiscovery();
  await client.commitDiscoveryPage(page());
});

test("known terminal/open-resource states are rejected before journaling an invalid request", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  await assert.rejects(
    client.finishDiscovery(),
    error("discovery_resources_open"),
  );
  await assert.rejects(
    client.finishDiscoveryResource({
      resource_key: "courses",
      outcome: "complete",
      reason: null,
    }),
    error("invalid_discovery_input"),
  );
  await client.commitDiscoveryPage(page());
  await assert.rejects(
    client.commitDiscoveryPage(page()),
    error("invalid_discovery_input"),
  );
  assert.equal(f.data[key].discovery.pending, null);
  await client.finishDiscoveryResource({
    resource_key: "courses",
    outcome: "complete",
    reason: null,
  });
  await client.finishDiscovery();
});

for (const stage of ["prepare", "delivery"]) {
  test(`credential expiry during profile read blocks ${stage}`, async () => {
    const f = fixture(),
      client = f.client();
    const realNow = Date.now,
      expiryAt = Date.parse(expires);
    let now = expiryAt - 1000,
      profiles = 0;
    Date.now = () => now;
    f.onProfile = () => {
      if (++profiles === (stage === "prepare" ? 1 : 2)) now = expiryAt;
    };
    try {
      await assert.rejects(
        client.beginDiscovery(),
        error("reconnect_required"),
      );
      assert.equal(f.rpc().length, stage === "prepare" ? 0 : 1);
      assert.deepEqual(f.data, {});
    } finally {
      Date.now = realNow;
    }
  });
}

test("all_active retains initial scan rows when completed discovery removes a course from context", async () => {
  const f = fixture(),
    client = f.client();
  f.context.mode = "all_active";
  f.context.course_ids = ["101"];
  f.context.resource_kinds = ["assignments"];
  await client.beginDiscovery();
  const empty = page();
  empty.items = [];
  await client.commitDiscoveryPage(empty);
  f.onSend = (action, body) => {
    if (action.endsWith("/resource") && body.resource_key === "courses")
      f.context.course_ids = [];
  };
  await client.finishDiscoveryResource({
    resource_key: "courses",
    outcome: "complete",
    reason: null,
  });
  await assert.rejects(
    client.finishDiscovery(),
    error("discovery_resources_open"),
  );
  assert.equal(f.data[key].discovery.pending, null);
  await client.finishDiscoveryResource({
    resource_key: "101/assignments",
    outcome: "unsupported",
    reason: "unsupported_format",
  });
  f.finishCoverage = "partial";
  assert.equal((await client.finishDiscovery()).coverage, "partial");
});

test("all_active adds newly discovered active resources to the durable scan ledger", async () => {
  const f = fixture(),
    client = f.client();
  f.context.mode = "all_active";
  f.context.resource_kinds = ["assignments"];
  await client.beginDiscovery();
  await client.commitDiscoveryPage(page());
  assert.ok(f.data[key].discovery.required.includes("101/assignments"));
  await client.finishDiscoveryResource({
    resource_key: "courses",
    outcome: "complete",
    reason: null,
  });
  await assert.rejects(
    client.finishDiscovery(),
    error("discovery_resources_open"),
  );
  await client.finishDiscoveryResource({
    resource_key: "101/assignments",
    outcome: "unsupported",
    reason: "unsupported_format",
  });
  f.finishCoverage = "partial";
  await client.finishDiscovery();
});

for (const corruption of ["missing_row", "false_complete"]) {
  test(`finish receipt cannot conceal an acknowledged incomplete resource: ${corruption}`, async () => {
    const f = fixture(),
      client = f.client();
    f.context.course_ids = ["101"];
    f.context.resource_kinds = ["assignments"];
    await client.beginDiscovery();
    await client.commitDiscoveryPage(page());
    await client.finishDiscoveryResource({
      resource_key: "courses",
      outcome: "complete",
      reason: null,
    });
    await client.finishDiscoveryResource({
      resource_key: "101/assignments",
      outcome: "unsupported",
      reason: "unsupported_format",
    });
    f.override = (operation, receipt) =>
      operation !== "finish"
        ? receipt
        : {
            ...receipt,
            coverage: "complete",
            resources: (corruption === "missing_row"
              ? receipt.resources.slice(0, 1)
              : receipt.resources
            ).map((r) => ({ ...r, coverage: "complete", reason: null })),
          };
    await assert.rejects(
      client.finishDiscovery(),
      error("discovery_outcome_unknown"),
    );
    assert.equal(f.data[key].discovery.pending.operation, "finish");
    f.override = null;
    assert.equal((await client.retryDiscovery()).coverage, "partial");
  });
}
