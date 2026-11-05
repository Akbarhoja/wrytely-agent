// Document phases live inside the existing discovery journal; no independent storage.
import { prepareDocumentParts } from "../canvas/document-parts.mjs";
import {
  canonicalSourceBytes,
  sourceDigest,
} from "../canvas/source-digest.mjs";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const reasons = new Set([
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
]);
const hash = /^[0-9a-f]{64}$/;
const clone = (x) => structuredClone(x);
function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((k) => [k, stable(value[k])]),
    );
  return value;
}
const same = (a, b) => JSON.stringify(stable(a)) === JSON.stringify(stable(b));

const exact = (x, keys) =>
  x &&
  typeof x === "object" &&
  !Array.isArray(x) &&
  Object.keys(x).length === keys.length &&
  keys.every((k) => Object.hasOwn(x, k));
export const documentOperation = (name) =>
  [
    "document_begin",
    "document_parts",
    "document_finish",
    "document_batch",
    "document_resource",
  ].includes(name);
function payload(header) {
  return {
    digest_version: 1,
    kind: "document",
    title: header.metadata.title,
    content: "",
    fields: {
      format: header.metadata.format,
      extractor_version: header.metadata.extractor_version,
      total_pages: header.metadata.total_pages,
      total_characters: header.metadata.total_characters,
      slots: header.manifest,
      owner_kind: header.owner_object.kind,
      object_fields: header.object_fields,
    },
    coverage: header.metadata.coverage,
    missing: header.metadata.missing,
  };
}
export function documentPipeline({
  prepare,
  available,
  enqueue,
  persist,
  fail,
  validExpiry,
  resourceKey,
  canvasOrigin,
}) {
  function validate(plan) {
    if (
      !exact(plan, [
        "resource_key",
        "observed_at",
        "next_cursor",
        "coverage",
        "documents",
        "index",
        "phase",
      ]) ||
      !resourceKey(plan.resource_key) ||
      plan.resource_key === "courses" ||
      !validExpiry(plan.observed_at) ||
      !["begin", "parts", "finish", "batch"].includes(plan.phase) ||
      !Number.isInteger(plan.index) ||
      plan.index < 0 ||
      !Array.isArray(plan.documents) ||
      plan.documents.length > 4 ||
      plan.index > plan.documents.length ||
      (plan.phase === "batch"
        ? plan.index !== plan.documents.length
        : plan.index === plan.documents.length)
    )
      throw Error();
    if (
      !exact(plan.coverage, ["state", "reason"]) ||
      !["complete", "partial", "restricted", "unsupported"].includes(
        plan.coverage.state,
      ) ||
      (plan.coverage.state === "complete"
        ? plan.coverage.reason !== null
        : !reasons.has(plan.coverage.reason)) ||
      !(
        plan.next_cursor === null ||
        (typeof plan.next_cursor === "string" &&
          plan.next_cursor.length > 0 &&
          plan.next_cursor.length <= 4000 &&
          plan.coverage.state === "partial" &&
          plan.coverage.reason === "more_pages")
      )
    )
      throw Error();
    const ids = new Set();
    for (const doc of plan.documents) {
      if (
        !exact(doc, [
          "header",
          "parts",
          "part_index",
          "reference",
          "digest",
          "upload_id",
          "document_version_id",
        ]) ||
        !hash.test(doc.digest) ||
        !(doc.upload_id === null || uuid.test(doc.upload_id)) ||
        !(
          doc.document_version_id === null || uuid.test(doc.document_version_id)
        ) ||
        !Array.isArray(doc.parts) ||
        doc.parts.length > 512 ||
        !Number.isInteger(doc.part_index) ||
        doc.part_index < 0 ||
        doc.part_index > doc.parts.length ||
        !exact(doc.header, [
          "resource",
          "owner_object",
          "object_fields",
          "metadata",
          "manifest",
        ])
      )
        throw Error();
      const h = doc.header;
      if (
        `${h.resource?.course_id}/${h.resource?.kind}` !== plan.resource_key ||
        !Array.isArray(h.manifest) ||
        h.manifest.length !== doc.parts.length
      )
        throw Error();
      canonicalSourceBytes(payload(h));
      const id = h.owner_object.kind + ":" + h.owner_object.provider_id;
      if (ids.has(id)) throw Error();
      ids.add(id);
      const url = new URL(doc.reference),
        base = `/courses/${h.resource.course_id}`;
      if (
        url.origin !== canvasOrigin ||
        !(url.pathname === base || url.pathname.startsWith(base + "/")) ||
        url.username ||
        url.password ||
        decodeURIComponent(url.pathname)
          .split("/")
          .some((p) => p === ".." || p === ".")
      )
        throw Error();
      for (const [slot, part] of doc.parts.entries())
        if (
          !exact(part, ["slot", "text"]) ||
          part.slot !== slot ||
          typeof part.text !== "string" ||
          [...part.text].length !==
            h.manifest[slot].end - h.manifest[slot].start
        )
          throw Error();
    }
  }
  function request(j, operation) {
    const plan = j.document,
      doc = plan.documents[plan.index];
    const common = {
      schema_version: 2,
      connection_id: j.binding.connection_id,
      generation: j.binding.generation,
      scan_id: j.scan.scan_id,
      subject: j.binding.subject,
      lease_token: j.scan.lease_token,
    };
    if (operation === "document_begin")
      return {
        ...common,
        operation: "begin_document",
        request_key: crypto.randomUUID(),
        ...clone(doc.header),
      };
    if (operation === "document_parts")
      return {
        ...common,
        operation: "put_document_parts",
        request_key: crypto.randomUUID(),
        upload_id: doc.upload_id,
        parts: clone(doc.parts.slice(doc.part_index, doc.part_index + 50)),
      };
    if (operation === "document_finish")
      return {
        ...common,
        operation: "finish_document",
        request_key: crypto.randomUUID(),
        upload_id: doc.upload_id,
      };
    const batch = crypto.randomUUID();
    return {
      scan_id: common.scan_id,
      generation: common.generation,
      lease_token: common.lease_token,
      batch_key: batch,
      expected_checkpoint: clone(j.scan.checkpoint),
      envelope: {
        schema_version: 2,
        batch_type: "canvas_documents",
        connection_id: common.connection_id,
        generation: common.generation,
        scan_id: common.scan_id,
        batch_key: batch,
        subject: common.subject,
        resource: {
          course_id: plan.resource_key.split("/")[0],
          kind: plan.resource_key.split("/")[1],
        },
        observed_at: plan.observed_at,
        items: plan.documents.map((d) => ({
          kind: d.header.owner_object.kind,
          provider_id: d.header.owner_object.provider_id,
          provider_updated_at: d.header.metadata.provider_updated_at,
          title: d.header.metadata.title,
          reference: d.reference,
          upload_id: d.upload_id,
        })),
        coverage: {
          ...plan.coverage,
          seen_count:
            (j.academic?.resource_key === plan.resource_key
              ? j.academic.seen_count
              : 0) + plan.documents.length,
        },
        next_cursor: plan.next_cursor,
      },
    };
  }
  function validateRequest(operation, body, j) {
    if (operation === "document_resource") {
      if (
        !exact(body, [
          "scan_id",
          "generation",
          "lease_token",
          "resource_key",
          "finish_key",
          "expected_checkpoint",
          "outcome",
          "reason",
        ]) ||
        !resourceKey(body.resource_key) ||
        body.resource_key === "courses" ||
        body.scan_id !== j.scan.scan_id ||
        body.generation !== j.binding.generation ||
        !uuid.test(body.lease_token) ||
        !uuid.test(body.finish_key)
      )
        throw Error();
      return;
    }
    validate(j.document);
    const plan = j.document,
      wanted = "document_" + plan.phase;
    if (operation !== wanted) throw Error();
    // The persisted request is the exact phase specification. Only the writer
    // lease may rotate on resume; keys never change after an unknown response.
    const expected = request(j, operation);
    const key = operation === "document_batch" ? "batch_key" : "request_key";
    expected[key] = body[key];
    if (operation === "document_batch") {
      expected.envelope.batch_key = body[key];
      const before = body.expected_checkpoint;
      const after = {
        ...before,
        resource: plan.resource_key,
        sequence: before?.sequence + 1,
        next_cursor: plan.next_cursor,
      };
      if (
        !exact(before, [
          "resource",
          "sequence",
          "next_cursor",
          "scope_revision",
        ]) ||
        !Number.isSafeInteger(before.sequence) ||
        before.sequence < 0 ||
        before.scope_revision !== j.binding.scope_revision ||
        (!same(j.scan.checkpoint, before) && !same(j.scan.checkpoint, after))
      )
        throw Error();
      expected.expected_checkpoint = clone(before);
    }
    if (
      !uuid.test(body[key]) ||
      !same({ ...body, lease_token: expected.lease_token }, expected)
    )
      throw Error();
  }
  async function acknowledge(j, response) {
    const { operation, body } = j.pending;
    if (operation === "document_resource") return false;
    const p = j.document,
      doc = p.documents[p.index];
    if (operation === "document_batch") {
      const expected = {
        ...body.expected_checkpoint,
        resource: p.resource_key,
        sequence: body.expected_checkpoint.sequence + 1,
        next_cursor: p.next_cursor,
      };
      if (
        response.schema_version !== 2 ||
        response.batch_type !== "canvas_documents" ||
        response.scan_id !== j.scan.scan_id ||
        response.batch_key !== body.batch_key ||
        !uuid.test(response.receipt_id) ||
        !hash.test(response.batch_digest) ||
        typeof response.replayed !== "boolean" ||
        response.coverage !== p.coverage.state ||
        !same(response.checkpoint, expected) ||
        !Array.isArray(response.observations) ||
        response.observations.length !== p.documents.length
      )
        throw Error();
      const remaining = new Map(
        p.documents.map((d) => [
          d.header.owner_object.kind + ":" + d.header.owner_object.provider_id,
          d,
        ]),
      );
      let incomplete =
        p.coverage.state !== "complete" && p.coverage.reason !== "more_pages";
      for (const row of response.observations) {
        const key = row.kind + ":" + row.provider_id,
          original = remaining.get(key);
        if (
          !original ||
          !uuid.test(row.object_id) ||
          !uuid.test(row.observation_id) ||
          row.document_version_id !== original.document_version_id ||
          row.document_digest !== original.digest ||
          row.coverage !== original.header.metadata.coverage ||
          typeof row.historical !== "boolean"
        )
          throw Error();
        remaining.delete(key);
        incomplete ||= row.coverage !== "complete" || row.historical;
      }
      const previous =
        j.academic?.resource_key === p.resource_key ? j.academic : null;
      j.academic = {
        resource_key: p.resource_key,
        seen_count: body.envelope.coverage.seen_count,
        page_count: (previous?.page_count ?? 0) + 1,
        last_page_coverage: p.coverage.state,
        incomplete: !!previous?.incomplete || incomplete,
      };
      j.incomplete_resource ||= j.academic.incomplete;
      j.scan.checkpoint = clone(response.checkpoint);
      j.document = null;
    } else {
      if (
        response.schema_version !== 2 ||
        response.operation !== body.operation ||
        !uuid.test(response.receipt_id) ||
        !uuid.test(response.upload_id) ||
        !validExpiry(response.expires_at) ||
        Date.parse(response.expires_at) <= Date.now() ||
        typeof response.replayed !== "boolean" ||
        (doc.upload_id !== null && response.upload_id !== doc.upload_id)
      )
        throw Error();
      if (operation === "document_begin") {
        if (
          !Array.isArray(response.received_slots) ||
          response.received_slots.length
        )
          throw Error();
        doc.upload_id = response.upload_id;
        p.phase = doc.parts.length ? "parts" : "finish";
      } else if (operation === "document_parts") {
        if (
          JSON.stringify(response.received_slots) !==
          JSON.stringify(
            doc.parts
              .slice(0, doc.part_index + body.parts.length)
              .map((x) => x.slot),
          )
        )
          throw Error();
        doc.part_index += body.parts.length;
        p.phase = doc.part_index === doc.parts.length ? "finish" : "parts";
      } else {
        if (
          response.ready !== true ||
          !uuid.test(response.document_version_id) ||
          response.document_digest !== doc.digest
        )
          throw Error();
        doc.document_version_id = response.document_version_id;
        p.index++;
        p.phase = p.index === p.documents.length ? "batch" : "begin";
      }
    }
    j.pending = null;
    return true;
  }
  const operations = {
    commitDocumentPage: async (input) => {
      const p = await prepare();
      available(p.j);
      let plan;
      try {
        const snapshot = clone(input),
          j = p.j;
        if (
          !exact(snapshot, [
            "resource_key",
            "observed_at",
            "next_cursor",
            "coverage",
            "documents",
          ]) ||
          !Array.isArray(snapshot.documents) ||
          snapshot.documents.length > 4 ||
          j.document ||
          !j.closed.includes("courses") ||
          !j.required.includes(snapshot.resource_key) ||
          j.closed.includes(snapshot.resource_key) ||
          j.scan.checkpoint.sequence >= 10000 ||
          (j.academic &&
            j.academic.resource_key !== snapshot.resource_key &&
            !j.closed.includes(j.academic.resource_key)) ||
          (j.academic?.resource_key === snapshot.resource_key &&
            (j.scan.checkpoint.next_cursor === null ||
              j.academic.page_count >= 100 ||
              j.academic.seen_count + snapshot.documents.length > 5000))
        )
          throw Error();
        const documents = [];
        for (const d of snapshot.documents) {
          if (
            !exact(d, [
              "owner_object",
              "object_fields",
              "metadata",
              "source",
              "reference",
            ])
          )
            throw Error();
          const prepared = await prepareDocumentParts(d.source);
          if (
            (d.metadata.format === "pdf_text") !==
            (prepared.total_pages !== null)
          )
            throw Error();
          if (
            prepared.unrepresented_pages.length &&
            (d.metadata.coverage === "complete" || !d.metadata.missing?.length)
          )
            throw Error();
          const [course_id, kind] = snapshot.resource_key.split("/");
          const header = {
            resource: { course_id, kind },
            owner_object: d.owner_object,
            object_fields: d.object_fields,
            metadata: {
              ...d.metadata,
              total_characters: prepared.total_characters,
              total_pages: prepared.total_pages,
            },
            manifest: prepared.manifest,
          };
          documents.push({
            header,
            parts: prepared.parts,
            part_index: 0,
            reference: d.reference,
            digest: await sourceDigest(payload(header)),
            upload_id: null,
            document_version_id: null,
          });
        }
        plan = {
          resource_key: snapshot.resource_key,
          observed_at: snapshot.observed_at,
          next_cursor: snapshot.next_cursor,
          coverage: snapshot.coverage,
          documents,
          index: 0,
          phase: documents.length ? "begin" : "batch",
        };
        validate(plan);
      } catch {
        fail("invalid_document_input");
      }
      p.j = { ...p.j, version: 3, document: plan };
      await persist(p, p.j);
      const operation = "document_" + plan.phase;
      return enqueue(p, operation, request(p.j, operation));
    },
    continueDocumentPage: async () => {
      const p = await prepare();
      available(p.j);
      if (!p.j.document) fail("document_not_active");
      const operation = "document_" + p.j.document.phase;
      return enqueue(p, operation, request(p.j, operation));
    },
    finishDocumentResource: async (input) => {
      const p = await prepare();
      available(p.j);
      const j = p.j,
        progress = j.academic;
      if (
        !exact(input, ["resource_key", "outcome", "reason"]) ||
        j.document ||
        !j.required.includes(input.resource_key) ||
        j.closed.includes(input.resource_key) ||
        progress?.resource_key !== input.resource_key ||
        (input.outcome === "complete"
          ? progress.incomplete ||
            progress.last_page_coverage !== "complete" ||
            j.scan.checkpoint.next_cursor !== null ||
            input.reason !== null
          : !["partial", "restricted", "unsupported"].includes(input.outcome) ||
            !reasons.has(input.reason))
      )
        fail("invalid_document_input");
      return enqueue(p, "document_resource", {
        scan_id: j.scan.scan_id,
        generation: j.binding.generation,
        lease_token: j.scan.lease_token,
        resource_key: input.resource_key,
        finish_key: crypto.randomUUID(),
        expected_checkpoint: clone(j.scan.checkpoint),
        outcome: input.outcome,
        reason: input.reason,
      });
    },
  };
  return { validate, validateRequest, acknowledge, operations };
}
