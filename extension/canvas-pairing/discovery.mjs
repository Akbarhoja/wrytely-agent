// Private worker helper. Public callers receive neither credentials nor writer leases.
import { collectCourseTick } from "./collector.mjs";
export const discoveryConflicts = [
  "checkpoint_changed",
  "course_not_discovered",
  "course_scope_limit",
  "cursor_cycle",
  "duplicate_course_page",
  "generation_changed",
  "identity_required",
  "incomplete_resource",
  "lease_expired",
  "lease_replaced",
  "pagination_complete_or_limit",
  "reconnect_required",
  "replay_conflict",
  "resource_not_selected",
  "resource_terminal",
  "resources_open",
  "resume_existing_scan",
  "scan_terminal",
  "scope_changed",
  "subject_changed",
];
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
const reasons = [
  "more_pages",
  "login_required",
  "permission_denied",
  "initial_post_required",
  "rate_limited",
  "provider_unavailable",
  "extraction_failed",
  "size_limit",
  "cursor_invalid",
  "unsupported_format",
];
const states = ["complete", "partial", "restricted", "unsupported"];
const MAX_RESOURCES = 54001; // (1000 initial +5000 discovered courses)*9 kinds +courses.
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const digest = /^[0-9a-f]{64}$/;
const keyPattern = /^[A-Za-z0-9._:-]{1,128}$/;
const integer = (x, max = Number.MAX_SAFE_INTEGER) =>
  Number.isSafeInteger(x) && x >= 0 && x <= max;
const chars = (x, max) =>
  typeof x === "string" &&
  !/[\u0000\uD800-\uDFFF]/u.test(x) &&
  [...x].length <= max;
const object = (x) => x !== null && typeof x === "object" && !Array.isArray(x);
const exact = (x, keys) =>
  object(x) &&
  Object.keys(x).length === keys.length &&
  keys.every((k) => Object.hasOwn(x, k));
const same = (a, b) =>
  a.resource === b.resource &&
  a.sequence === b.sequence &&
  a.next_cursor === b.next_cursor &&
  a.scope_revision === b.scope_revision;
const bytes = (x) => new TextEncoder().encode(JSON.stringify(x)).length;
const clone = (x) => structuredClone(x);
const resourceKey = (x) =>
  x === "courses" ||
  (typeof x === "string" &&
    /^[1-9][0-9]{0,19}\//.test(x) &&
    kinds.includes(x.split("/")[1]) &&
    x.split("/").length === 2);

export function discoveryOperations({
  run,
  record,
  currentContext,
  subject,
  call,
  save,
  fail,
  cleanup,
  invalidateAccount,
  canvasOrigin,
  validExpiry,
  readCoursePage,
}) {
  function checkpoint(value, revision) {
    if (
      !exact(value, [
        "resource",
        "sequence",
        "next_cursor",
        "scope_revision",
      ]) ||
      value.resource !== "courses" ||
      !integer(value.sequence, 100) ||
      value.scope_revision !== revision ||
      !(
        value.next_cursor === null ||
        (chars(value.next_cursor, 4000) && value.next_cursor.length > 0)
      )
    )
      throw Error();
    return clone(value);
  }
  function lease(value, revision) {
    if (
      !object(value) ||
      !uuid.test(value.scan_id) ||
      !uuid.test(value.lease_token) ||
      !integer(value.scan_sequence) ||
      value.scan_sequence < 1 ||
      !validExpiry(value.lease_expires_at)
    )
      throw Error();
    return {
      scan_id: value.scan_id,
      scan_sequence: value.scan_sequence,
      lease_token: value.lease_token,
      lease_expires_at: value.lease_expires_at,
      checkpoint: checkpoint(value.checkpoint, revision),
    };
  }
  function outcome(value, key) {
    return (
      states.includes(value.outcome) &&
      (value.outcome === "complete"
        ? key === "courses" && value.reason === null
        : reasons.includes(value.reason))
    );
  }
  function validatePage(value) {
    if (
      !exact(value, ["items", "observed_at", "next_cursor", "coverage"]) ||
      !validExpiry(value.observed_at) ||
      !Array.isArray(value.items) ||
      value.items.length > 50 ||
      !exact(value.coverage, ["state", "reason"]) ||
      !states.includes(value.coverage.state)
    )
      throw Error();
    if (
      value.coverage.state === "complete"
        ? value.coverage.reason !== null
        : !reasons.includes(value.coverage.reason)
    )
      throw Error();
    if (!(
      value.next_cursor === null ||
      (chars(value.next_cursor, 4000) &&
        value.next_cursor.length > 0 &&
        value.coverage.state === "partial" &&
        value.coverage.reason === "more_pages")
    ))
      throw Error();
    const ids = new Set();
    for (const item of value.items) {
      if (
        !exact(item, [
          "provider_id",
          "provider_updated_at",
          "title",
          "reference",
          "content",
          "fields",
          "coverage",
          "missing",
        ]) ||
        typeof item.provider_id !== "string" ||
        !/^[1-9][0-9]{0,19}$/.test(item.provider_id) ||
        ids.has(item.provider_id) ||
        !(
          item.provider_updated_at === null ||
          chars(item.provider_updated_at, Number.MAX_SAFE_INTEGER)
        ) ||
        !chars(item.title, 500) ||
        item.reference !== `${canvasOrigin}/courses/${item.provider_id}` ||
        item.content !== "" ||
        !exact(item.fields, ["course_code", "timezone", "enrollment_state"]) ||
        Object.values(item.fields).some((v) => v !== null && !chars(v, 500)) ||
        !states.includes(item.coverage) ||
        !Array.isArray(item.missing) ||
        item.missing.length > 50 ||
        item.missing.some((s) => !chars(s, Number.MAX_SAFE_INTEGER)) ||
        (item.coverage === "complete" && item.missing.length)
      )
        throw Error();
      ids.add(item.provider_id);
    }
  }
  function validateBody(operation, body, j) {
    const fields = {
      begin: [
        "connection_id",
        "generation",
        "subject",
        "scope_revision",
        "begin_key",
      ],
      batch: [
        "scan_id",
        "generation",
        "lease_token",
        "batch_key",
        "expected_checkpoint",
        "envelope",
      ],
      resource: [
        "scan_id",
        "generation",
        "lease_token",
        "resource_key",
        "finish_key",
        "expected_checkpoint",
        "outcome",
        "reason",
      ],
      finish: ["scan_id", "generation", "lease_token", "finish_key"],
      resume: ["scan_id", "generation", "resume_key"],
    };
    if (
      !exact(body, fields[operation] ?? []) ||
      body.generation !== j.binding.generation
    )
      throw Error();
    const requestKey =
      body.begin_key ?? body.batch_key ?? body.finish_key ?? body.resume_key;
    if (typeof requestKey !== "string" || !keyPattern.test(requestKey))
      throw Error();
    if (operation === "begin") {
      if (
        body.connection_id !== j.binding.connection_id ||
        body.subject !== j.binding.subject ||
        body.scope_revision !== j.binding.scope_revision
      )
        throw Error();
      return;
    }
    if (
      !j.scan ||
      body.scan_id !== j.scan.scan_id ||
      (operation !== "resume" && !uuid.test(body.lease_token))
    )
      throw Error();
    if (body.expected_checkpoint)
      checkpoint(body.expected_checkpoint, j.binding.scope_revision);
    if (
      operation === "resource" &&
      (!resourceKey(body.resource_key) || !outcome(body, body.resource_key))
    )
      throw Error();
    if (operation === "batch") {
      const e = body.envelope;
      if (
        !exact(e, [
          "schema_version",
          "connection_id",
          "generation",
          "scan_id",
          "batch_key",
          "subject",
          "resource",
          "observed_at",
          "items",
          "coverage",
          "next_cursor",
        ]) ||
        e.schema_version !== 1 ||
        e.connection_id !== j.binding.connection_id ||
        e.generation !== body.generation ||
        e.scan_id !== body.scan_id ||
        e.batch_key !== body.batch_key ||
        e.subject !== j.binding.subject ||
        !exact(e.resource, ["course_id", "kind"]) ||
        e.resource.course_id !== null ||
        e.resource.kind !== "courses" ||
        !exact(e.coverage, ["state", "reason", "seen_count"]) ||
        e.coverage.seen_count !== j.seen_count + e.items?.length ||
        !integer(e.coverage.seen_count, 5000) ||
        bytes(e) > 1024 * 1024
      )
        throw Error();
      validatePage({
        items: e.items,
        observed_at: e.observed_at,
        coverage: { state: e.coverage.state, reason: e.coverage.reason },
        next_cursor: e.next_cursor,
      });
    }
  }
  function journal(value) {
    if (value === undefined) return null;
    try {
      if (
        bytes(value) > 8 * 1024 * 1024 ||
        !exact(value, [
          "version",
          "binding",
          "scan",
          "seen_count",
          "last_page_coverage",
          "scope_mode",
          "resource_kinds",
          "required",
          "incomplete_resource",
          "pending",
          "renewal",
          "closed",
          "finished",
        ]) ||
        value.version !== 1 ||
        !exact(value.binding, [
          "connection_id",
          "generation",
          "scope_revision",
          "subject",
        ]) ||
        !uuid.test(value.binding.connection_id) ||
        !integer(value.binding.generation) ||
        value.binding.generation < 1 ||
        !integer(value.binding.scope_revision) ||
        typeof value.binding.subject !== "string" ||
        !/^[1-9][0-9]{0,127}$/.test(value.binding.subject) ||
        !integer(value.seen_count, 5000) ||
        typeof value.incomplete_resource !== "boolean" ||
        !["explicit_set", "all_active"].includes(value.scope_mode) ||
        !Array.isArray(value.resource_kinds) ||
        value.resource_kinds.length > 9 ||
        value.resource_kinds.some((k) => !kinds.includes(k)) ||
        new Set(value.resource_kinds).size !== value.resource_kinds.length ||
        !Array.isArray(value.required) ||
        value.required.length > MAX_RESOURCES ||
        !value.required.includes("courses") ||
        value.required.some((k) => !resourceKey(k)) ||
        new Set(value.required).size !== value.required.length ||
        !(
          value.last_page_coverage === null ||
          states.includes(value.last_page_coverage)
        ) ||
        !Array.isArray(value.closed) ||
        value.closed.length > MAX_RESOURCES ||
        value.closed.some((k) => !resourceKey(k)) ||
        new Set(value.closed).size !== value.closed.length
      )
        throw Error();
      const required = new Set(value.required);
      if (value.closed.some((k) => !required.has(k))) throw Error();
      if (value.scan !== null) {
        if (
          !exact(value.scan, [
            "scan_id",
            "scan_sequence",
            "lease_token",
            "lease_expires_at",
            "checkpoint",
          ])
        )
          throw Error();
        lease(value.scan, value.binding.scope_revision);
      }
      if (value.pending !== null) {
        if (
          !exact(value.pending, ["operation", "body"]) ||
          !["begin", "batch", "resource", "finish"].includes(
            value.pending.operation,
          )
        )
          throw Error();
        validateBody(value.pending.operation, value.pending.body, value);
      }
      if (value.renewal !== null) validateBody("resume", value.renewal, value);
      if (
        value.finished !== null &&
        (!exact(value.finished, ["coverage", "resource_count"]) ||
          !["complete", "partial"].includes(value.finished.coverage) ||
          !integer(value.finished.resource_count, MAX_RESOURCES) ||
          value.pending ||
          value.renewal)
      )
        throw Error();
      if (!value.scan !== (value.pending?.operation === "begin")) throw Error();
      return clone(value);
    } catch {
      fail("discovery_journal_invalid");
    }
  }
  async function persist(p, j) {
    if (bytes(j) > 8 * 1024 * 1024) fail("discovery_size_limit");
    await save(p.item, j);
  }
  function status(j) {
    if (!j) return { state: "idle" };
    return {
      state: j.finished
        ? "finished"
        : j.pending || j.renewal
          ? "pending"
          : "active",
      generation: j.binding.generation,
      scope_revision: j.binding.scope_revision,
      pending: j.renewal ? "resume" : (j.pending?.operation ?? null),
      needs_resume:
        !!j.scan && Date.parse(j.scan.lease_expires_at) <= Date.now(),
      seen_count: j.seen_count,
      closed_count: j.closed.length,
      coverage: j.finished?.coverage ?? null,
    };
  }
  function result(j) {
    return {
      ...status(j),
      checkpoint: j.scan ? clone(j.scan.checkpoint) : null,
      closed_resources: [...j.closed],
    };
  }
  async function profile(item, expected) {
    let value;
    try {
      value = await subject();
    } catch {
      fail("canvas_session_unavailable");
    }
    if (expected !== undefined && value !== expected)
      return invalidateAccount(item, value);
    return value;
  }
  async function prepare(newScan = false) {
    let item = await record();
    if (!item) return cleanup("reconnect_required");
    const j = journal(item.discovery);
    const context = await currentContext(item);
    item = await record();
    if (
      !item ||
      context.connection_id !== item.connection.connection_id ||
      context.generation !== item.connection.generation
    )
      fail("discovery_context_changed");
    if (context.state !== "connected") fail("discovery_identity_required");
    const currentSubject = await profile(item, j?.binding.subject);
    if (Date.parse(context.credential_expires_at) <= Date.now())
      return cleanup("reconnect_required");
    if (
      j &&
      !(newScan && j.finished) &&
      (j.binding.connection_id !== context.connection_id ||
        j.binding.generation !== context.generation ||
        j.binding.scope_revision !== context.scope_revision ||
        j.scope_mode !== context.mode ||
        JSON.stringify(j.resource_kinds) !==
          JSON.stringify(context.resource_kinds))
    )
      fail("discovery_context_changed");
    return { item, j, context, subject: currentSubject };
  }
  async function finalCheck(p, j) {
    const item = await record();
    if (!item) return cleanup("reconnect_required");
    const context = await currentContext(item);
    if (
      j.binding.connection_id !== context.connection_id ||
      j.binding.generation !== context.generation ||
      j.binding.scope_revision !== context.scope_revision
    )
      fail("discovery_context_changed");
    await profile(item, j.binding.subject);
    if (Date.parse(context.credential_expires_at) <= Date.now())
      return cleanup("reconnect_required");
    return result(j);
  }
  async function rpc(p, operation, body) {
    try {
      return await call(operation, body, p.item);
    } catch (e) {
      if (e?.code === "reconnect_required")
        return cleanup("reconnect_required");
      if (e?.code === "discovery_subject_changed")
        return cleanup("canvas_account_changed");
      throw e;
    }
  }
  function acknowledge(j, response) {
    const { operation, body } = j.pending;
    if (operation === "begin") {
      const scan = lease(response, j.binding.scope_revision);
      if (
        scan.checkpoint.sequence !== 0 ||
        scan.checkpoint.next_cursor !== null
      )
        throw Error();
      j.scan = scan;
    } else if (operation === "batch") {
      const expected = {
        ...body.expected_checkpoint,
        sequence: body.expected_checkpoint.sequence + 1,
        next_cursor: body.envelope.next_cursor,
      };
      const got = checkpoint(response.checkpoint, j.binding.scope_revision);
      if (
        !uuid.test(response.receipt_id) ||
        response.scan_id !== j.scan.scan_id ||
        response.batch_key !== body.batch_key ||
        !digest.test(response.batch_digest) ||
        !Array.isArray(response.source_versions) ||
        response.source_versions.length ||
        response.coverage !== body.envelope.coverage.state ||
        typeof response.replayed !== "boolean" ||
        !same(got, expected) ||
        !(
          same(j.scan.checkpoint, body.expected_checkpoint) ||
          same(j.scan.checkpoint, expected)
        )
      )
        throw Error();
      j.scan.checkpoint = got;
      j.seen_count = body.envelope.coverage.seen_count;
      j.last_page_coverage = body.envelope.coverage.state;
      // Preserve metadata gaps from earlier pages without forking journal storage.
      if (body.envelope.items.some((item) => item.coverage !== "complete"))
        j.incomplete_resource = true;
      if (j.scope_mode === "all_active") {
        const required = new Set(j.required);
        for (const item of body.envelope.items)
          if (item.fields.enrollment_state === "active")
            for (const kind of j.resource_kinds)
              required.add(`${item.provider_id}/${kind}`);
        if (required.size > MAX_RESOURCES) throw Error();
        j.required = [...required];
      }
    } else if (operation === "resource") {
      if (
        !uuid.test(response.receipt_id) ||
        response.resource_key !== body.resource_key ||
        response.coverage !== body.outcome ||
        response.reason !== body.reason ||
        !integer(response.seen_count, 5000) ||
        !validExpiry(response.finished_at) ||
        !(
          response.source_manifest_digest === null ||
          (typeof response.source_manifest_digest === "string" &&
            digest.test(response.source_manifest_digest))
        ) ||
        typeof response.replayed !== "boolean" ||
        !same(
          checkpoint(response.checkpoint, j.binding.scope_revision),
          j.scan.checkpoint,
        )
      )
        throw Error();
      if (!j.closed.includes(body.resource_key))
        j.closed.push(body.resource_key);
      if (body.outcome !== "complete") j.incomplete_resource = true;
    } else {
      const required = new Set(j.required);
      if (
        response.scan_id !== j.scan.scan_id ||
        !["complete", "partial"].includes(response.coverage) ||
        typeof response.replayed !== "boolean" ||
        !Array.isArray(response.resources) ||
        response.resources.length > MAX_RESOURCES ||
        response.resources.length !== required.size ||
        response.resources.some(
          (r) =>
            !resourceKey(r.resource_key) ||
            !required.has(r.resource_key) ||
            !states.includes(r.coverage) ||
            (r.coverage === "complete"
              ? r.reason !== null
              : !reasons.includes(r.reason)),
        ) ||
        new Set(response.resources.map((r) => r.resource_key)).size !==
          response.resources.length ||
        (response.coverage === "complete" &&
          (j.incomplete_resource ||
            response.resources.some((r) => r.coverage !== "complete")))
      )
        throw Error();
      j.finished = {
        coverage: response.coverage,
        resource_count: response.resources.length,
      };
    }
    j.pending = null;
  }
  async function sendPending(p) {
    const j = clone(p.j);
    if (!j?.pending) fail("discovery_no_pending_operation");
    if (j.renewal) fail("discovery_pending_operation");
    if (j.pending.operation !== "begin") {
      j.pending.body.lease_token = j.scan.lease_token;
      await persist(p, j);
    }
    const response = await rpc(p, j.pending.operation, j.pending.body);
    try {
      acknowledge(j, response);
    } catch {
      fail("discovery_outcome_unknown");
    }
    await persist(p, j);
    return finalCheck(p, j);
  }
  function available(j) {
    if (!j?.scan || j.finished) fail("discovery_not_active");
    if (j.pending || j.renewal) fail("discovery_pending_operation");
    if (Date.parse(j.scan.lease_expires_at) <= Date.now())
      fail("discovery_lease_expired");
  }
  async function enqueue(p, operation, body) {
    try {
      validateBody(operation, body, p.j);
    } catch {
      fail("invalid_discovery_input");
    }
    const j = clone(p.j);
    j.pending = { operation, body: clone(body) };
    await persist(p, j);
    return sendPending({ ...p, j });
  }
  const operations = {
    beginDiscovery: async () => {
      const p = await prepare(true);
      if (p.j && !p.j.finished) fail("discovery_pending_operation");
      p.j = {
        version: 1,
        binding: {
          connection_id: p.context.connection_id,
          generation: p.context.generation,
          scope_revision: p.context.scope_revision,
          subject: p.subject,
        },
        scan: null,
        seen_count: 0,
        last_page_coverage: null,
        scope_mode: p.context.mode,
        resource_kinds: [...p.context.resource_kinds],
        required: [
          "courses",
          ...p.context.course_ids.flatMap((course) =>
            p.context.resource_kinds.map((kind) => `${course}/${kind}`),
          ),
        ],
        incomplete_resource: false,
        pending: null,
        renewal: null,
        closed: [],
        finished: null,
      };
      return enqueue(p, "begin", {
        ...p.j.binding,
        begin_key: crypto.randomUUID(),
      });
    },
    retryDiscovery: async () => sendPending(await prepare()),
    resumeDiscovery: async () => {
      const p = await prepare(),
        j = clone(p.j);
      if (!j?.scan || j.finished)
        fail(j?.pending ? "discovery_pending_begin" : "discovery_not_active");
      if (!j.renewal) {
        j.renewal = {
          scan_id: j.scan.scan_id,
          generation: j.binding.generation,
          resume_key: crypto.randomUUID(),
        };
        await persist(p, j);
      }
      let response;
      try {
        response = await rpc(p, "resume", j.renewal);
      } catch (e) {
        if (
          e?.code === "discovery_request_rejected" ||
          discoveryConflicts.some((code) => e?.code === `discovery_${code}`)
        ) {
          // A controlled rejection has no accepted resume receipt; do not strand primary recovery.
          j.renewal = null;
          await persist(p, j);
        }
        throw e;
      }
      let next;
      try {
        next = lease(response, j.binding.scope_revision);
        if (
          next.scan_id !== j.scan.scan_id ||
          next.scan_sequence !== j.scan.scan_sequence
        )
          throw Error();
      } catch {
        fail("discovery_outcome_unknown");
      }
      const expected =
        j.pending?.operation === "batch"
          ? {
              ...j.pending.body.expected_checkpoint,
              sequence: j.pending.body.expected_checkpoint.sequence + 1,
              next_cursor: j.pending.body.envelope.next_cursor,
            }
          : null;
      if (
        !same(next.checkpoint, j.scan.checkpoint) &&
        !(expected && same(next.checkpoint, expected))
      )
        fail("discovery_reconciliation_required");
      j.scan = next;
      j.renewal = null;
      await persist(p, j);
      return finalCheck(p, j);
    },
    commitDiscoveryPage: async (input) => {
      const p = await prepare();
      available(p.j);
      try {
        validatePage(input);
        if (
          p.j.scan.checkpoint.sequence >= 100 ||
          p.j.closed.includes("courses") ||
          (p.j.scan.checkpoint.sequence > 0 &&
            p.j.scan.checkpoint.next_cursor === null) ||
          p.j.seen_count + input.items.length > 5000
        )
          throw Error();
      } catch {
        fail("invalid_discovery_input");
      }
      const batchKey = crypto.randomUUID(),
        j = p.j;
      return enqueue(p, "batch", {
        scan_id: j.scan.scan_id,
        generation: j.binding.generation,
        lease_token: j.scan.lease_token,
        batch_key: batchKey,
        expected_checkpoint: clone(j.scan.checkpoint),
        envelope: {
          schema_version: 1,
          connection_id: j.binding.connection_id,
          generation: j.binding.generation,
          subject: j.binding.subject,
          scan_id: j.scan.scan_id,
          batch_key: batchKey,
          resource: { course_id: null, kind: "courses" },
          observed_at: input.observed_at,
          items: clone(input.items),
          coverage: {
            ...input.coverage,
            seen_count: j.seen_count + input.items.length,
          },
          next_cursor: input.next_cursor,
        },
      });
    },
    finishDiscoveryResource: async (input) => {
      const p = await prepare();
      available(p.j);
      if (
        !exact(input, ["resource_key", "outcome", "reason"]) ||
        !resourceKey(input.resource_key) ||
        !outcome(input, input.resource_key)
      )
        fail("invalid_discovery_input");
      if (p.j.closed.includes(input.resource_key))
        fail("discovery_resource_closed");
      if (
        input.outcome === "complete" &&
        (p.j.last_page_coverage !== "complete" ||
          p.j.scan.checkpoint.next_cursor !== null)
      )
        fail("invalid_discovery_input");
      if (!p.j.required.includes(input.resource_key))
        fail("invalid_discovery_input");
      return enqueue(p, "resource", {
        scan_id: p.j.scan.scan_id,
        generation: p.j.binding.generation,
        lease_token: p.j.scan.lease_token,
        finish_key: crypto.randomUUID(),
        expected_checkpoint: clone(p.j.scan.checkpoint),
        ...input,
      });
    },
    finishDiscovery: async () => {
      const p = await prepare();
      available(p.j);
      const closed = new Set(p.j.closed);
      if (p.j.required.some((key) => !closed.has(key)))
        fail("discovery_resources_open");
      return enqueue(p, "finish", {
        scan_id: p.j.scan.scan_id,
        generation: p.j.binding.generation,
        lease_token: p.j.scan.lease_token,
        finish_key: crypto.randomUUID(),
      });
    },
    readDiscoveryStatus: async () => {
      const item = await record(),
        j = journal(item?.discovery);
      if (
        j &&
        (j.binding.connection_id !== item.connection.connection_id ||
          j.binding.generation !== item.connection.generation)
      )
        return { state: "blocked", reason: "discovery_context_changed" };
      return status(j);
    },
  };
  operations.collectCoursePage = () =>
    collectCourseTick({
      operations,
      origin: canvasOrigin,
      conflicts: discoveryConflicts,
      readPage: readCoursePage,
      inspect: async () => {
        const { j } = await prepare();
        return {
          ...status(j),
          checkpoint: j?.scan ? clone(j.scan.checkpoint) : null,
          last_page_coverage: j?.last_page_coverage ?? null,
          incomplete: j?.incomplete_resource ?? false,
          courses_closed: j?.closed.includes("courses") ?? false,
          open_resources: j
            ? j.required.filter((key) => !j.closed.includes(key)).length
            : 0,
        };
      },
    });
  // All operations, including the whole capture/commit tick, share the original lock.
  return Object.fromEntries(
    Object.entries(operations).map(([name, operation]) => [
      name,
      (...args) => run(() => operation(...args)),
    ]),
  );
}
