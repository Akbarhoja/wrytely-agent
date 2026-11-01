// Worker-only binding/validation. Reuse the provider mapper; never retain raw data.
import { mapAssignmentObservation } from "../canvas/assignment-observation.mjs";
import { canonicalSourceBytes } from "../canvas/source-digest.mjs";

const states = ["complete", "partial", "restricted", "unsupported"];
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
const object = (x) => x !== null && typeof x === "object" && !Array.isArray(x);
const exact = (x, keys) =>
  object(x) &&
  Object.keys(x).length === keys.length &&
  keys.every((k) => Object.hasOwn(x, k));
const chars = (x, max) =>
  typeof x === "string" &&
  !/[\u0000\uD800-\uDFFF]/u.test(x) &&
  [...x].length <= max;
const bytes = (x) => new TextEncoder().encode(JSON.stringify(x)).length;
const fields = [
  "due_at",
  "unlock_at",
  "lock_at",
  "points_possible",
  "submission_types",
  "rubric",
  "published",
];

export const assignmentKey = (key) =>
  typeof key === "string" && /^[1-9][0-9]{0,19}\/assignments$/.test(key);

function portable(value, depth = 0) {
  if (depth > 16) throw Error();
  if (typeof value === "string" && !chars(value, Number.MAX_SAFE_INTEGER))
    throw Error();
  if (Array.isArray(value)) value.forEach((x) => portable(x, depth + 1));
  else if (object(value))
    Object.values(value).forEach((x) => portable(x, depth + 1));
}

export function validateAssignmentPage(value, origin, timestamp) {
  if (
    !exact(value, [
      "resource_key",
      "observed_at",
      "next_cursor",
      "coverage",
      "items",
    ]) ||
    !assignmentKey(value.resource_key) ||
    !timestamp(value.observed_at) ||
    !Array.isArray(value.items) ||
    value.items.length > 50 ||
    !exact(value.coverage, ["state", "reason"]) ||
    !states.includes(value.coverage.state) ||
    (value.coverage.state === "complete"
      ? value.coverage.reason !== null
      : !reasons.includes(value.coverage.reason)) ||
    !(
      value.next_cursor === null ||
      (chars(value.next_cursor, 4000) &&
        value.next_cursor.length > 0 &&
        value.coverage.state === "partial" &&
        value.coverage.reason === "more_pages")
    )
  )
    throw Error();
  const course = value.resource_key.split("/")[0],
    seen = new Set();
  for (const item of value.items) {
    if (
      !exact(item, [
        "kind",
        "provider_id",
        "provider_updated_at",
        "title",
        "reference",
        "content",
        "fields",
        "coverage",
        "missing",
      ]) ||
      item.kind !== "assignment" ||
      typeof item.provider_id !== "string" ||
      !/^[1-9][0-9]{0,19}$/.test(item.provider_id) ||
      seen.has(item.provider_id) ||
      !(
        item.provider_updated_at === null || timestamp(item.provider_updated_at)
      ) ||
      !chars(item.title, 300) ||
      !chars(item.content, 24000) ||
      item.reference !==
        `${origin}/courses/${course}/assignments/${item.provider_id}` ||
      !exact(item.fields, fields) ||
      !states.includes(item.coverage) ||
      !Array.isArray(item.missing) ||
      item.missing.length > 50 ||
      (item.coverage === "complete" &&
        (item.missing.length || !item.title.trim() || !item.content.trim()))
    )
      throw Error();
    seen.add(item.provider_id);
    portable(item.fields);
    const normalized = JSON.parse(
      new TextDecoder().decode(
        canonicalSourceBytes({
          digest_version: 1,
          kind: "assignment",
          title: item.title,
          content: item.content,
          fields: item.fields,
          coverage: item.coverage,
          missing: item.missing,
        }),
      ),
    );
    const remapped = mapAssignmentObservation(
      {
        ...item.fields,
        id: item.provider_id,
        course_id: course,
        name: item.title,
      },
      {
        courseId: course,
        dateContext: "requesting_student",
        extracted: {
          courseId: course,
          assignmentId: item.provider_id,
          text: item.content,
          coverage: item.coverage,
          missing: item.missing,
        },
      },
    ).digestPayload;
    if (
      item.title !== normalized.title ||
      item.content !== normalized.content ||
      JSON.stringify(item.fields) !== JSON.stringify(normalized.fields) ||
      JSON.stringify(item.missing) !== JSON.stringify(normalized.missing) ||
      JSON.stringify(normalized) !== JSON.stringify(remapped)
    )
      throw Error();
  }
}

export function prepareAssignmentPage(input, origin, timestamp) {
  try {
    if (
      !exact(input, [
        "resource_key",
        "observed_at",
        "next_cursor",
        "coverage",
        "items",
      ]) ||
      !assignmentKey(input.resource_key) ||
      !Array.isArray(input.items) ||
      input.items.length > 50 ||
      bytes(input) > 2 * 1024 * 1024
    )
      throw Error();
    const course = input.resource_key.split("/")[0];
    const items = input.items.map((source) => {
      if (
        !object(source) ||
        ![2, 3].includes(Object.keys(source).length) ||
        !Object.hasOwn(source, "raw") ||
        !Object.hasOwn(source, "extracted") ||
        Object.keys(source).some(
          (k) => !["raw", "extracted", "dateContext"].includes(k),
        )
      )
        throw Error();
      const mapped = mapAssignmentObservation(source.raw, {
        courseId: course,
        extracted: source.extracted,
        dateContext: source.dateContext ?? "unverified",
      });
      const { title, content, fields, coverage, missing } =
        mapped.digestPayload;
      const id = mapped.providerIdentity.provider_id;
      return {
        kind: "assignment",
        provider_id: id,
        provider_updated_at: source.raw.updated_at ?? null,
        title,
        reference: `${origin}/courses/${course}/assignments/${id}`,
        content,
        fields,
        coverage,
        missing,
      };
    });
    const result = { ...structuredClone(input), items };
    if (
      result.coverage?.state === "complete" &&
      items.some((item) => item.coverage !== "complete")
    )
      result.coverage = { state: "partial", reason: "extraction_failed" };
    validateAssignmentPage(result, origin, timestamp);
    return result;
  } catch {
    throw Error("invalid_assignment_input");
  }
}
