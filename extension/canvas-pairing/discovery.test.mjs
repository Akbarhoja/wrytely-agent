import { test } from "node:test";
import assert from "node:assert/strict";
import { sourceDigest } from "../canvas/source-digest.mjs";
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
    pageCalls: [],
    assignmentCalls: [],
    assignmentResponses: [],
    courseResponses: [],
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
    if (action === "academic/extract") {
      if (f.onExtract) await f.onExtract(body);
      const result = {
        course_id: body.course_id,
        items: body.items.map((item) => ({
          assignment_id: item.assignment_id,
          text: item.html === null ? "" : "PRIVATE_EXTRACTED_TEXT",
          coverage: "partial",
          missing: ["html_text_only"],
        })),
      };
      return json(f.extractOverride ? f.extractOverride(result) : result, url);
    }
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
      if (["batch", "resource", "finish"].includes(operation) && f.expiredLease)
        return json({ detail: { code: "lease_expired" } }, url, 409);
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
        if (operation === "resume") {
          f.leases++;
          f.expiredLease = false;
        }
        result = {
          scan_id: id(2),
          scan_sequence: 1,
          lease_token: id(f.leases + 10),
          lease_expires_at: expires,
          checkpoint: structuredClone(f.checkpoint),
        };
      } else if (operation === "batch") {
        const academic = action.startsWith("academic/");
        if (
          JSON.stringify(body.expected_checkpoint) !==
          JSON.stringify(f.checkpoint)
        )
          return json({ detail: { code: "checkpoint_changed" } }, url, 409);
        f.applied++;
        if (!academic && f.context.mode === "all_active")
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
          resource: academic
            ? `${body.envelope.resource.course_id}/${body.envelope.resource.kind}`
            : "courses",
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
        if (academic) {
          const row = f.resources.find(
            (r) => r.resource_key === f.checkpoint.resource,
          );
          row.seen_count = body.envelope.coverage.seen_count;
          row.page_count = (row.page_count ?? 0) + 1;
          row.incomplete =
            row.incomplete ||
            body.envelope.items.some((i) => i.coverage !== "complete") ||
            f.historical;
          row.last_page_coverage = body.envelope.coverage.state;
          row.next_cursor = body.envelope.next_cursor;
          result.observations = await Promise.all(
            body.envelope.items.map(async (item, index) => ({
              provider_id: item.provider_id,
              kind: "assignment",
              observation_id: id(500 + f.applied * 50 + index),
              version_id:
                item.content.trim() && item.title.trim()
                  ? id(300 + f.applied * 50 + index)
                  : null,
              content_digest: await sourceDigest({
                digest_version: 1,
                kind: item.kind,
                title: item.title,
                content: item.content,
                fields: item.fields,
                coverage: item.coverage,
                missing: item.missing,
              }),
              coverage: item.coverage,
              historical: !!f.historical,
            })),
          );
          result.source_versions = result.observations
            .filter((o) => o.version_id !== null)
            .map(({ provider_id, version_id, content_digest }) => ({
              provider_id,
              version_id,
              content_digest,
            }));
        }
      } else if (operation === "resource") {
        const row = f.resources.find(
          (r) => r.resource_key === body.resource_key,
        );
        if (!row)
          return json({ detail: { code: "resource_not_selected" } }, url, 409);
        if (
          action.startsWith("academic/") &&
          body.outcome === "complete" &&
          (!row.page_count ||
            row.incomplete ||
            row.last_page_coverage !== "complete" ||
            row.next_cursor !== null)
        )
          return json({ detail: { code: "incomplete_resource" } }, url, 409);
        row.coverage = body.outcome;
        row.reason = body.reason;
        result = {
          receipt_id: id(80),
          resource_key: body.resource_key,
          coverage: body.outcome,
          reason: body.reason,
          seen_count: action.startsWith("academic/")
            ? (row.seen_count ?? 0)
            : f.applied,
          finished_at: expires,
          checkpoint: structuredClone(f.checkpoint),
          source_manifest_digest:
            action.startsWith("academic/") && body.outcome === "complete"
              ? "b".repeat(64)
              : null,
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
      canvasFetch: async (url) => {
        if (new URL(url).pathname === "/api/v1/courses/101/assignments") {
          f.assignmentCalls.push(url);
          if (f.onAssignmentRequest) await f.onAssignmentRequest();
          const value = f.assignmentResponses.shift() ?? {
            data: assignmentPage().items.map((item) => item.raw),
          };
          const response = json(value.data, url, value.status ?? 200);
          if (value.next)
            response.headers.set("link", `<${value.next}>; rel="next"`);
          return response;
        }
        if (new URL(url).pathname === "/api/v1/courses") {
          f.pageCalls.push(url);
          if (f.onCourseRequest) await f.onCourseRequest();
          if (f.pageError) throw Error("PRIVATE_PROVIDER_FAILURE");
          const page = f.courseResponses.shift() ?? {
            data: [
              {
                id: 101,
                name: "PRIVATE_COURSE",
                course_code: "SYN-101",
                time_zone: "America/Denver",
                enrollments: [{ enrollment_state: "active" }],
              },
            ],
          };
          const response = json(page.data, url, f.pageStatus ?? 200);
          if (page.next)
            response.headers.set("link", `<${page.next}>; rel="next"`);
          return response;
        }
        if (f.onProfile) await f.onProfile();
        return Response.json({ id: f.profiles.shift() ?? "7" });
      },
    });
  f.rpc = () =>
    f.calls.filter(
      (c) =>
        c.action.startsWith("discovery/") || c.action.startsWith("academic/"),
    );
  return f;
}

const courseCursor = `${canvasOrigin}/api/v1/courses?enrollment_state=active&per_page=50&page=opaque`;
const rawCourse = (id, extra = {}) => ({
  id,
  name: "PRIVATE_COURSE",
  course_code: "SYN",
  time_zone: "America/Denver",
  enrollments: [{ enrollment_state: "active" }],
  ...extra,
});

const assignmentPage = (id = 17, cursor = null) => ({
  resource_key: "101/assignments",
  observed_at: "2026-11-01T00:00:00Z",
  next_cursor: cursor,
  coverage: {
    state: cursor ? "partial" : "complete",
    reason: cursor ? "more_pages" : null,
  },
  items: [
    {
      raw: {
        id,
        course_id: 101,
        name: "PRIVATE_ASSIGNMENT_TITLE",
        description: "PRIVATE_RAW_HTML",
        due_at: null,
        unlock_at: null,
        lock_at: null,
        points_possible: 20,
        submission_types: ["online_upload"],
        rubric: [],
        published: true,
      },
      extracted: {
        courseId: 101,
        assignmentId: id,
        text: "PRIVATE_EXTRACTED_TEXT",
        coverage: "complete",
        missing: [],
      },
      dateContext: "requesting_student",
    },
  ],
});
async function readyAssignment(f) {
  f.context.mode = "all_active";
  f.context.resource_kinds = ["assignments"];
  const client = f.client();
  await client.beginDiscovery();
  await client.commitDiscoveryPage(page());
  await client.finishDiscoveryResource({
    resource_key: "courses",
    outcome: "complete",
    reason: null,
  });
  return client;
}
const closeAssignment = (client, outcome = "complete") =>
  client.finishAssignmentResource({
    resource_key: "101/assignments",
    outcome,
    reason: outcome === "complete" ? null : "extraction_failed",
  });

test("assignment collector fetches and extracts one page then closes honest partial coverage", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  const first = await client.collectAssignmentPage();
  assert.equal(first.action, "assignment_page");
  assert.equal(f.assignmentCalls.length, 1);
  assert.equal(f.data[key].discovery.academic.seen_count, 1);
  assert.ok(!JSON.stringify(f.data[key]).includes("PRIVATE_RAW_HTML"));
  assert.ok(!JSON.stringify(first).includes("PRIVATE_EXTRACTED_TEXT"));
  assert.equal(
    (await f.client().collectAssignmentPage()).action,
    "close_assignments",
  );
  assert.equal((await f.client().collectAssignmentPage()).coverage, "partial");
  assert.equal(f.assignmentCalls.length, 1);
});

test("assignment collector recovers accepted pending capture without provider refetch", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  f.onSend = (action) => {
    if (action === "academic/batch") {
      f.loss = "after";
      f.onSend = null;
    }
  };
  assert.equal(
    (await client.collectAssignmentPage()).reason,
    "discovery_outcome_unknown",
  );
  const capture = structuredClone(f.data[key].discovery.pending.body);
  assert.equal((await f.client().collectAssignmentPage()).action, "recover");
  assert.deepEqual(f.rpc().at(-1).body, capture);
  assert.equal(f.assignmentCalls.length, 1);
});

for (const control of ["scope", "account", "expiry"])
  test(`assignment collector fences ${control} before extraction upload`, async () => {
    const f = fixture(),
      client = await readyAssignment(f);
    f.onAssignmentRequest = () => {
      if (control === "scope") f.context.scope_revision++;
      if (control === "account") f.profiles.push("8");
      if (control === "expiry")
        f.context.credential_expires_at = "2000-01-01T00:00:00Z";
    };
    const result = await client.collectAssignmentPage();
    assert.equal(result.state, "blocked");
    assert.equal(
      f.calls.filter((c) => c.action === "academic/extract").length,
      0,
    );
    assert.equal(
      f.calls.filter((c) => c.action === "academic/batch").length,
      0,
    );
  });

for (const corruption of ["course", "id", "missing", "complete"])
  test(`assignment collector rejects invalid extraction ${corruption}`, async () => {
    const f = fixture(),
      client = await readyAssignment(f);
    f.extractOverride = (result) => {
      if (corruption === "course") result.course_id = "102";
      if (corruption === "id") result.items[0].assignment_id = "999";
      if (corruption === "missing") result.items = [];
      if (corruption === "complete") result.items[0].coverage = "complete";
      return result;
    };
    const result = await client.collectAssignmentPage();
    assert.equal(result.state, "blocked");
    assert.equal(f.data[key].discovery.pending, null);
    assert.equal(
      f.calls.filter((c) => c.action === "academic/batch").length,
      0,
    );
  });

test("assignment collector fences context changed during extraction", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  f.onExtract = () => {
    f.context.scope_revision++;
  };
  assert.equal((await client.collectAssignmentPage()).state, "blocked");
  assert.equal(f.calls.filter((c) => c.action === "academic/batch").length, 0);
});

test("assignment collector preserves same storage lock during provider fetch", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  let release, entered;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const started = new Promise((resolve) => {
    entered = resolve;
  });
  f.onAssignmentRequest = async () => {
    entered();
    await gate;
  };
  const collecting = client.collectAssignmentPage();
  await started;
  await assert.rejects(
    f.client().readDiscoveryStatus(),
    error("operation_in_progress"),
  );
  release();
  await collecting;
});

test("assignment collector follows one page per explicit tick and never fetches locked description", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  const cursor = `${canvasOrigin}/api/v1/courses/101/assignments?per_page=50&override_assignment_dates=true&page=opaque`;
  const locked = assignmentPage(18).items[0].raw;
  locked.locked_for_user = true;
  f.assignmentResponses = [
    { data: [assignmentPage(17).items[0].raw], next: cursor },
    { data: [locked] },
  ];
  await client.collectAssignmentPage();
  assert.equal(f.assignmentCalls.length, 1);
  await f.client().collectAssignmentPage();
  assert.deepEqual(f.assignmentCalls, [cursor.split("&page=")[0], cursor]);
  assert.equal(f.data[key].discovery.academic.seen_count, 2);
  const extracts = f.calls.filter((c) => c.action === "academic/extract");
  assert.equal(extracts[1].body.items[0].html, null);
  assert.equal(
    (await f.client().collectAssignmentPage()).action,
    "close_assignments",
  );
  assert.equal((await f.client().collectAssignmentPage()).coverage, "partial");
});

test("assignment collector does not fetch removed scope or hide provider denial", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  f.context.course_ids = [];
  assert.equal(
    (await client.collectAssignmentPage()).reason,
    "discovery_resource_not_selected",
  );
  assert.equal(f.assignmentCalls.length, 0);
  const g = fixture(),
    other = await readyAssignment(g);
  g.assignmentResponses = [{ status: 401, data: { private: "not logged" } }];
  assert.equal((await other.collectAssignmentPage()).reason, "login_required");
  assert.equal(g.data[key].discovery.pending, null);
});

test("assignment collector stops repeated provider reads at the known page ceiling", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  const next = `${canvasOrigin}/api/v1/courses/101/assignments?per_page=50&override_assignment_dates=true&page=opaque`;
  await client.commitAssignmentPage(assignmentPage(17, next));
  f.data[key].discovery.academic.page_count = 100;
  for (let tick = 0; tick < 2; tick++)
    assert.equal(
      (await f.client().collectAssignmentPage()).reason,
      "invalid_assignment_input",
    );
  assert.equal(f.assignmentCalls.length, 0);
  assert.equal(
    f.calls.filter((c) => c.action === "academic/extract").length,
    0,
  );
});

test("assignment journal posts mapped content then validates resource manifest", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  const result = await client.commitAssignmentPage(assignmentPage());
  assert.equal(result.checkpoint.resource, "101/assignments");
  assert.equal(f.data[key].discovery.version, 2);
  assert.equal(f.data[key].discovery.academic.seen_count, 1);
  assert.ok(!JSON.stringify(f.data[key]).includes("PRIVATE_RAW_HTML"));
  assert.ok(!JSON.stringify(result).includes("PRIVATE_EXTRACTED_TEXT"));
  assert.equal(f.rpc().at(-1).action, "academic/batch");
  await closeAssignment(client);
  assert.equal(f.rpc().at(-1).action, "academic/resource");
  assert.equal((await client.finishDiscovery()).coverage, "complete");
});

test("legacy pending course acknowledgment upgrades without changing captured body/key", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.loss = "after";
  await assert.rejects(
    client.commitDiscoveryPage(page()),
    error("discovery_outcome_unknown"),
  );
  const legacy = f.data[key].discovery;
  legacy.version = 1;
  delete legacy.academic;
  const captured = structuredClone(legacy.pending.body);
  await f.client().retryDiscovery();
  assert.equal(f.data[key].discovery.version, 2);
  assert.deepEqual(f.rpc().at(-1).body, captured);
  assert.equal(f.applied, 1);
});

for (const operation of ["begin", "resource", "finish", "resume"]) {
  test(`legacy pending ${operation} preserves its original captured intent through upgrade`, async () => {
    const f = fixture(),
      client = f.client();
    if (operation !== "begin") {
      await client.beginDiscovery();
      await client.commitDiscoveryPage(page());
    }
    if (operation === "finish")
      await client.finishDiscoveryResource({
        resource_key: "courses",
        outcome: "complete",
        reason: null,
      });
    f.loss = "after";
    const dispatch =
      operation === "begin"
        ? client.beginDiscovery()
        : operation === "resume"
          ? client.resumeDiscovery()
          : operation === "finish"
            ? client.finishDiscovery()
            : client.finishDiscoveryResource({
                resource_key: "courses",
                outcome: "complete",
                reason: null,
              });
    await assert.rejects(dispatch, error("discovery_outcome_unknown"));
    const legacy = f.data[key].discovery;
    legacy.version = 1;
    delete legacy.academic;
    const captured = structuredClone(
      operation === "resume" ? legacy.renewal : legacy.pending.body,
    );
    if (operation === "resume") await f.client().resumeDiscovery();
    else await f.client().retryDiscovery();
    assert.deepEqual(f.rpc().at(-1).body, captured);
    assert.equal(f.data[key].discovery.version, 2);
  });
}

for (const loss of ["before", "after"]) {
  test(`assignment capture survives restart after ${loss} dispatch loss`, async () => {
    const f = fixture(),
      client = await readyAssignment(f);
    f.loss = loss;
    await assert.rejects(
      client.commitAssignmentPage(assignmentPage()),
      error("discovery_outcome_unknown"),
    );
    const captured = structuredClone(f.data[key].discovery.pending.body);
    assert.equal(f.data[key].discovery.pending.operation, "academic_batch");
    await f.client().retryDiscovery();
    assert.deepEqual(f.rpc().at(-1).body, captured);
    assert.equal(f.data[key].discovery.academic.seen_count, 1);
    assert.equal(f.applied, 2);
  });
}

test("assignment lost accepted ack reconciles advanced resource checkpoint on resume", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  f.loss = "after";
  await assert.rejects(
    client.commitAssignmentPage(assignmentPage()),
    error("discovery_outcome_unknown"),
  );
  const captured = structuredClone(f.data[key].discovery.pending.body);
  await f.client().resumeDiscovery();
  await f.client().retryDiscovery();
  const sent = f.rpc().at(-1).body;
  assert.equal(sent.batch_key, captured.batch_key);
  assert.deepEqual(sent.envelope, captured.envelope);
  assert.notEqual(sent.lease_token, captured.lease_token);
  assert.equal(f.data[key].discovery.academic.page_count, 1);
});

for (const historical of [false, true]) {
  test(`incomplete assignment evidence cannot be closed complete: historical=${historical}`, async () => {
    const f = fixture(),
      client = await readyAssignment(f);
    f.historical = historical;
    const first = assignmentPage(17, "PRIVATE_NEXT");
    if (!historical) first.items[0].raw.rubric = null;
    await client.commitAssignmentPage(first);
    f.historical = false;
    await client.commitAssignmentPage(assignmentPage(18));
    await assert.rejects(
      closeAssignment(client),
      error("invalid_assignment_input"),
    );
    await closeAssignment(client, "partial");
    assert.equal((await client.finishDiscovery()).coverage, "partial");
  });
}

for (const variant of [
  "missing_observation",
  "wrong_version",
  "historical_type",
  "wrong_resource",
]) {
  test(`malformed academic receipt retains exact pending page: ${variant}`, async () => {
    const f = fixture(),
      client = await readyAssignment(f);
    f.override = (operation, result) => {
      if (operation !== "batch" || !result.observations) return result;
      if (variant === "missing_observation") result.observations = [];
      if (variant === "wrong_version")
        result.source_versions[0].version_id = id(999);
      if (variant === "historical_type")
        result.observations[0].historical = "false";
      if (variant === "wrong_resource")
        result.checkpoint.resource = "102/assignments";
      return result;
    };
    await assert.rejects(
      client.commitAssignmentPage(assignmentPage()),
      error("discovery_outcome_unknown"),
    );
    const saved = structuredClone(f.data[key].discovery.pending.body);
    f.override = null;
    await f.client().retryDiscovery();
    assert.deepEqual(f.rpc().at(-1).body, saved);
  });
}

test("assignment input cannot choose an unselected course or run before courses close", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  await assert.rejects(
    client.commitAssignmentPage(assignmentPage()),
    error("invalid_assignment_input"),
  );
  const g = fixture(),
    ready = await readyAssignment(g),
    input = assignmentPage();
  input.resource_key = "102/assignments";
  await assert.rejects(
    ready.commitAssignmentPage(input),
    error("invalid_assignment_input"),
  );
  assert.equal(
    g.rpc().filter((c) => c.action.startsWith("academic/")).length,
    0,
  );
});

test("v1 record cannot smuggle an academic checkpoint across migration", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  const legacy = f.data[key].discovery;
  legacy.version = 1;
  delete legacy.academic;
  legacy.scan.checkpoint.resource = "101/assignments";
  await assert.rejects(
    client.readDiscoveryStatus(),
    error("discovery_journal_invalid"),
  );
});

test("stored academic course identity must retain strict wire string type", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  f.loss = "before";
  await assert.rejects(client.commitAssignmentPage(assignmentPage()));
  f.data[key].discovery.pending.body.envelope.resource.course_id = 101;
  await assert.rejects(
    f.client().retryDiscovery(),
    error("discovery_journal_invalid"),
  );
});

test("begin receipt cannot jump directly to an academic resource", async () => {
  const f = fixture(),
    client = f.client();
  f.override = (operation, reply) => {
    if (operation === "begin") reply.checkpoint.resource = "101/assignments";
    return reply;
  };
  await assert.rejects(
    client.beginDiscovery(),
    error("discovery_outcome_unknown"),
  );
  assert.equal(f.data[key].discovery.pending.operation, "begin");
  f.override = null;
  await f.client().retryDiscovery();
});

test("matching receipt digests cannot substitute another captured source payload", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  f.override = (operation, reply) => {
    if (reply.observations) {
      reply.observations[0].content_digest = "f".repeat(64);
      reply.source_versions[0].content_digest = "f".repeat(64);
    }
    return reply;
  };
  await assert.rejects(
    client.commitAssignmentPage(assignmentPage()),
    error("discovery_outcome_unknown"),
  );
  assert.equal(f.data[key].discovery.academic, null);
  f.override = null;
  await f.client().retryDiscovery();
});

test("academic envelope accounts for server JSON spacing before persisting intent", async () => {
  const f = fixture(),
    client = await readyAssignment(f),
    input = assignmentPage();
  input.items = Array.from({ length: 50 }, (_, index) => {
    const item = assignmentPage(index + 1).items[0];
    item.extracted.text = "x".repeat(20580);
    return item;
  });
  const before = f.rpc().length;
  await assert.rejects(
    client.commitAssignmentPage(input),
    error("invalid_discovery_input"),
  );
  assert.equal(f.rpc().length, before);
  assert.equal(f.data[key].discovery.pending, null);
});

test("assignment progress starts at zero for each selected course and requires prior closure", async () => {
  const f = fixture();
  f.context.course_ids = ["101", "102"];
  const client = await readyAssignment(f);
  await client.commitAssignmentPage(assignmentPage());
  const second = assignmentPage();
  second.resource_key = "102/assignments";
  second.items[0].raw.course_id = 102;
  second.items[0].extracted.courseId = 102;
  await assert.rejects(
    client.commitAssignmentPage(second),
    error("invalid_assignment_input"),
  );
  await closeAssignment(client);
  await client.commitAssignmentPage(second);
  assert.equal(f.data[key].discovery.academic.seen_count, 1);
  assert.equal(f.data[key].discovery.academic.page_count, 1);
  assert.equal(f.data[key].discovery.scan.checkpoint.sequence, 3);
  await client.finishAssignmentResource({
    resource_key: "102/assignments",
    outcome: "complete",
    reason: null,
  });
  assert.equal((await client.finishDiscovery()).coverage, "complete");
});

for (const control of ["scope", "account", "expiry"]) {
  test(`assignment replay remains fenced after ${control} change`, async () => {
    const f = fixture(),
      client = await readyAssignment(f);
    f.loss = "after";
    await assert.rejects(
      client.commitAssignmentPage(assignmentPage()),
      error("discovery_outcome_unknown"),
    );
    const count = f.rpc().length;
    if (control === "scope") f.context.scope_revision++;
    if (control === "account") f.profiles.push("8");
    if (control === "expiry")
      f.context.credential_expires_at = "2000-01-01T00:00:00Z";
    await assert.rejects(f.client().retryDiscovery());
    assert.equal(f.rpc().length, count);
  });
}

test("assignment intent persistence failure prevents dispatch and acknowledgment failure permits exact retry", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  const count = f.rpc().length;
  f.storageFailure = (state, when) =>
    state.pending?.operation === "academic_batch" && when === "before";
  await assert.rejects(client.commitAssignmentPage(assignmentPage()));
  assert.equal(f.rpc().length, count);
  f.storageFailure = (state, when) =>
    state.academic !== null && state.pending === null && when === "before";
  await assert.rejects(client.commitAssignmentPage(assignmentPage()));
  const captured = structuredClone(f.data[key].discovery.pending.body);
  f.storageFailure = null;
  await f.client().retryDiscovery();
  assert.deepEqual(f.rpc().at(-1).body, captured);
  assert.equal(f.applied, 2);
});

test("assignment resource receipt requires matching count and manifest before closure", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  await client.commitAssignmentPage(assignmentPage());
  f.override = (operation, reply) =>
    operation === "resource"
      ? { ...reply, source_manifest_digest: null }
      : reply;
  await assert.rejects(
    closeAssignment(client),
    error("discovery_outcome_unknown"),
  );
  assert.ok(!f.data[key].discovery.closed.includes("101/assignments"));
  const captured = structuredClone(f.data[key].discovery.pending.body);
  f.override = null;
  await f.client().retryDiscovery();
  assert.deepEqual(f.rpc().at(-1).body, captured);
  assert.ok(f.data[key].discovery.closed.includes("101/assignments"));
});

test("assignment resource can close partial without a page but cannot close complete", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  await assert.rejects(
    closeAssignment(client),
    error("invalid_assignment_input"),
  );
  await closeAssignment(client, "partial");
  assert.equal((await client.finishDiscovery()).coverage, "partial");
});

test("assignment journal rejects another page after terminal capture and enforces page limit", async () => {
  const f = fixture(),
    client = await readyAssignment(f);
  await client.commitAssignmentPage(assignmentPage());
  await assert.rejects(
    client.commitAssignmentPage(assignmentPage(18)),
    error("invalid_assignment_input"),
  );
  const g = fixture(),
    other = await readyAssignment(g);
  await other.commitAssignmentPage(assignmentPage(17, "opaque"));
  g.data[key].discovery.academic.page_count = 100;
  await assert.rejects(
    other.commitAssignmentPage(assignmentPage(18)),
    error("invalid_assignment_input"),
  );
});

test("collector begins, captures one page, closes courses then awaits academic resources", async () => {
  const f = fixture();
  f.context.mode = "all_active";
  f.context.resource_kinds = ["assignments"];
  const client = f.client();
  assert.equal((await client.collectCoursePage()).action, "begin");
  assert.equal(f.pageCalls.length, 0);
  const result = await client.collectCoursePage();
  assert.equal(result.action, "page");
  assert.equal(result.seen_count, 1);
  assert.equal(f.pageCalls.length, 1);
  const body = f.rpc().find((c) => c.action.endsWith("/batch")).body;
  assert.equal(body.envelope.items[0].title, "PRIVATE_COURSE");
  for (const secret of [
    "PRIVATE",
    "lease_token",
    "subject",
    "checkpoint",
    token,
    canvasOrigin,
  ])
    assert.ok(!JSON.stringify(result).includes(secret));
  assert.equal((await client.collectCoursePage()).action, "close_courses");
  assert.equal((await client.collectCoursePage()).state, "awaiting_resources");
  assert.equal(f.pageCalls.length, 1);
  assert.ok(
    f.resources.some(
      (r) => r.resource_key === "101/assignments" && r.coverage === "open",
    ),
  );
});

test("collector terminal metadata-only scan finishes without fetching again", async () => {
  const f = fixture(),
    client = f.client();
  for (const action of ["begin", "page", "close_courses", "finish"])
    assert.equal((await client.collectCoursePage()).action, action);
  assert.equal((await client.collectCoursePage()).state, "finished");
  assert.equal(f.pageCalls.length, 1);
});

for (const loss of ["before", "after"]) {
  test(`collector restart replays exact captured page after ${loss}-commit loss`, async () => {
    const f = fixture(),
      client = f.client();
    await client.collectCoursePage();
    f.loss = loss;
    assert.equal((await client.collectCoursePage()).state, "blocked");
    const saved = structuredClone(f.data[key].discovery.pending.body);
    assert.equal((await f.client().collectCoursePage()).action, "recover");
    const sends = f.rpc().filter((c) => c.action.endsWith("/batch"));
    assert.deepEqual(sends[1].body, saved);
    assert.equal(f.applied, 1);
    assert.equal(f.pageCalls.length, 1);
  });
}

test("collector lease renewal and lost resume ack never recapture pending source", async () => {
  const f = fixture(),
    client = f.client();
  await client.collectCoursePage();
  f.loss = "before";
  await client.collectCoursePage();
  const saved = structuredClone(f.data[key].discovery.pending.body);
  f.data[key].discovery.scan.lease_expires_at = "2020-01-01T00:00:00Z";
  f.expiredLease = true;
  f.loss = "after";
  assert.equal((await f.client().collectCoursePage()).state, "blocked");
  assert.equal((await f.client().collectCoursePage()).action, "resume");
  assert.equal((await f.client().collectCoursePage()).action, "recover");
  const replay = f
    .rpc()
    .filter((c) => c.action.endsWith("/batch"))
    .at(-1).body;
  assert.equal(replay.batch_key, saved.batch_key);
  assert.deepEqual(replay.envelope, saved.envelope);
  assert.equal(f.pageCalls.length, 1);
  assert.equal(f.applied, 1);
});

test("collector replays accepted finish receipt before renewing an expired lease", async () => {
  const f = fixture(),
    client = f.client();
  for (let i = 0; i < 3; i++) await client.collectCoursePage();
  f.loss = "after";
  assert.equal(
    (await client.collectCoursePage()).reason,
    "discovery_outcome_unknown",
  );
  const saved = structuredClone(f.data[key].discovery.pending.body);
  f.data[key].discovery.scan.lease_expires_at = "2020-01-01T00:00:00Z";
  f.expiredLease = true;
  f.resumeError = "scan_terminal";
  const result = await f.client().collectCoursePage();
  assert.equal(result.state, "finished");
  assert.equal(result.action, "recover");
  assert.equal(f.rpc().filter((c) => c.action.endsWith("/resume")).length, 0);
  assert.deepEqual(
    f
      .rpc()
      .filter((c) => c.action.endsWith("/finish"))
      .at(-1).body,
    saved,
  );
  assert.equal(f.pageCalls.length, 1);
});

test("collector handles lease replacement with bounded resume then recovery", async () => {
  const f = fixture(),
    client = f.client();
  await client.collectCoursePage();
  f.leases++;
  assert.equal(
    (await client.collectCoursePage()).reason,
    "discovery_lease_replaced",
  );
  assert.equal((await client.collectCoursePage()).action, "resume");
  assert.equal((await client.collectCoursePage()).action, "recover");
  assert.equal(f.pageCalls.length, 1);
});

test("early metadata gap survives a later complete terminal page", async () => {
  const f = fixture(),
    client = f.client();
  f.courseResponses = [
    { data: [rawCourse(101, { course_code: null })], next: courseCursor },
    { data: [rawCourse(102)] },
  ];
  await client.collectCoursePage();
  await client.collectCoursePage();
  await client.collectCoursePage();
  assert.equal(f.pageCalls.length, 2);
  assert.equal(f.pageCalls[1], courseCursor);
  await client.collectCoursePage();
  assert.equal(f.resources[0].coverage, "partial");
  assert.equal((await client.collectCoursePage()).coverage, "partial");
});

test("provider denial preserves checkpoint and open resource; later explicit tick can recover", async () => {
  const f = fixture(),
    client = f.client();
  await client.collectCoursePage();
  f.pageStatus = 401;
  assert.deepEqual(await client.collectCoursePage(), {
    state: "blocked",
    reason: "login_required",
  });
  assert.equal(f.data[key].discovery.scan.checkpoint.sequence, 0);
  assert.equal(f.data[key].discovery.pending, null);
  assert.equal(f.resources[0].coverage, "open");
  f.pageStatus = 200;
  assert.equal((await client.collectCoursePage()).action, "page");
});

for (const change of ["account", "scope", "expiry"]) {
  test(`collector fences ${change} change between capture and commit`, async () => {
    const f = fixture(),
      client = f.client();
    await client.collectCoursePage();
    f.onCourseRequest = () => {
      if (change === "account") f.profiles.push("8");
      else if (change === "scope") f.context.scope_revision++;
      else f.context.credential_expires_at = "2020-01-01T00:00:00Z";
    };
    assert.equal((await client.collectCoursePage()).state, "blocked");
    assert.equal(f.rpc().filter((c) => c.action.endsWith("/batch")).length, 0);
    assert.equal(f.applied, 0);
  });
}

test("collector holds the existing storage lock throughout provider capture", async () => {
  const f = fixture(),
    client = f.client();
  await client.collectCoursePage();
  let release, entered;
  const ready = new Promise((resolve) => {
    entered = resolve;
  });
  const held = new Promise((resolve) => {
    release = resolve;
  });
  f.onCourseRequest = async () => {
    entered();
    await held;
  };
  const pending = client.collectCoursePage();
  await ready;
  await assert.rejects(
    f.client().readDiscoveryStatus(),
    error("operation_in_progress"),
  );
  release();
  assert.equal((await pending).action, "page");
});

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
test("an explicit new scan replaces a server-fenced old scope without re-pairing or replaying its pending upload", async () => {
  const f = fixture(),
    client = f.client();
  await client.beginDiscovery();
  f.loss = "before";
  await assert.rejects(
    client.commitDiscoveryPage(page()),
    error("discovery_outcome_unknown"),
  );
  f.context.generation++;
  f.context.scope_revision++;
  f.checkpoint.scope_revision = f.context.scope_revision;
  f.context.course_ids = ["101"];
  f.context.resource_kinds = ["assignments"];
  await assert.rejects(
    client.retryDiscovery(),
    error("discovery_context_changed"),
  );
  const before = f.rpc().length;
  await client.beginDiscovery();
  assert.equal(f.rpc().length, before + 1);
  assert.equal(f.rpc().at(-1).action, "discovery/begin");
  assert.equal(f.data[key].discovery.binding.generation, 2);
  assert.equal(f.data[key].discovery.binding.scope_revision, 1);
  assert.equal(f.data[key].discovery.pending, null);
  assert.ok(f.data[key].discovery.required.includes("101/assignments"));
});
for (const change of [
  "generation_only",
  "scope_only",
  "account",
  "credential",
]) {
  test(`new-scan scope recovery rejects ${change} without replacing the old journal`, async () => {
    const f = fixture(),
      client = f.client();
    await client.beginDiscovery();
    if (change !== "scope_only") f.context.generation++;
    if (change !== "generation_only") f.context.scope_revision++;
    if (change === "account") f.profiles.push("8");
    if (change === "credential") {
      f.unauthorized = true;
      f.context.state = "reconnect_required";
    }
    await assert.rejects(client.beginDiscovery());
    assert.equal(
      f.rpc().filter((x) => x.action === "discovery/begin").length,
      1,
    );
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

for (const mode of ["all_active", "explicit_set"]) {
  test(`empty ${mode} completion preserves only configured discovery intent`, async () => {
    const f = fixture(),
      client = f.client();
    f.context.mode = mode;
    f.context.resource_kinds = ["assignments"];
    await client.beginDiscovery();
    await client.commitDiscoveryPage({ ...page(), items: [] });
    await client.finishDiscoveryResource({
      resource_key: "courses",
      outcome: "complete",
      reason: null,
    });
    await client.finishDiscovery();
    assert.equal(
      (await client.readDiscoveryStatus()).content_requested,
      mode === "all_active",
    );
    f.context.resource_kinds = [];
    assert.equal((await client.readDiscoveryStatus()).content_requested, false);
  });
}
