// Offline provider mapping only. Inputs do not establish user identity or permission.
import { canonicalSourceBytes } from "./source-digest.mjs";

export class AssignmentMappingError extends TypeError {
  constructor(code) {
    super(code);
    this.code = code;
  }
}
const fail = (code) => {
  throw new AssignmentMappingError(code);
};
const object = (value) =>
  value !== null &&
  typeof value === "object" &&
  !Array.isArray(value) &&
  [Object.prototype, null].includes(Object.getPrototypeOf(value));
const COVERAGE = new Set(["complete", "partial", "restricted", "unsupported"]);
const CRITERION = new Set([
  "id",
  "description",
  "long_description",
  "points",
  "ratings",
  "criterion_use_range",
  "ignore_for_scoring",
  "learning_outcome_id",
  "vendor_guid",
]);
const RATING = new Set(["id", "description", "long_description", "points"]);

function providerId(value) {
  if (typeof value === "number" && (!Number.isSafeInteger(value) || value < 1))
    fail("invalid_identity");
  if (
    !["string", "number"].includes(typeof value) ||
    !/^[1-9][0-9]{0,19}$/.test(String(value))
  )
    fail("invalid_identity");
  return String(value);
}
function boundedText(value, limit, code, nullable = true) {
  if (nullable && value == null) return null;
  if (
    typeof value !== "string" ||
    value.length > limit * 2 ||
    [...value].length > limit
  )
    fail(code);
  return value;
}
function nullableBoolean(value, code) {
  if (value == null) return null;
  if (typeof value !== "boolean") fail(code);
  return value;
}

function decimal(value, allowNegative = false) {
  if (value == null) return null;
  const numeric = typeof value === "number";
  if (
    numeric &&
    (!Number.isFinite(value) || Math.abs(value) > Number.MAX_SAFE_INTEGER)
  )
    fail("invalid_points");
  if (!numeric && typeof value !== "string") fail("invalid_points");
  const source = String(value);
  if (source.length > 64) fail("invalid_points");
  const pattern = numeric
    ? /^(-?)(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/
    : /^(-?)(\d+)(?:\.(\d+))?$/;
  const match = pattern.exec(source);
  if (!match || match[0] !== source) fail("invalid_points");
  const [, sign, whole, fraction = "", exponent = "0"] = match;
  if (sign && !allowNegative) fail("invalid_points");
  const position = whole.length + Number(exponent);
  const digits = whole + fraction;
  if (Math.abs(position) > 64 || digits.length > 64) fail("invalid_points");
  let expanded =
    position <= 0
      ? "0." + "0".repeat(-position) + digits
      : position >= digits.length
        ? digits + "0".repeat(position - digits.length)
        : digits.slice(0, position) + "." + digits.slice(position);
  let [integer, part = ""] = expanded.split(".");
  integer = integer.replace(/^0+(?=\d)/, "");
  part = part.replace(/0+$/, "");
  expanded = integer + (part ? "." + part : "");
  if (expanded.length > 64) fail("invalid_points");
  return (sign && expanded !== "0" ? "-" : "") + expanded;
}

function rubricId(value) {
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) fail("invalid_rubric");
    value = String(value);
  }
  if (typeof value !== "string" || !value.length || value.length > 256)
    fail("invalid_rubric");
  // Check uniqueness in the same NFC/LF domain used by C2 serialization.
  return value.replace(/\r\n?/g, "\n").normalize("NFC");
}
function rubricRows(value, ratings, missing) {
  if (value == null) return null;
  if (!Array.isArray(value) || value.length > (ratings ? 50 : 100))
    fail("invalid_rubric");
  const ids = new Set();
  return value.map((row) => {
    if (!object(row)) fail("invalid_rubric");
    const allowed = ratings ? RATING : CRITERION;
    if (Object.keys(row).some((key) => !allowed.has(key)))
      fail("unsupported_rubric_field");
    for (const key of ratings
      ? ["description", "points"]
      : ["description", "points", "ratings"]) {
      if (!Object.hasOwn(row, key) || row[key] === undefined) {
        missing.push(`rubric_${ratings ? "rating_" : ""}${key}_not_observed`);
      }
    }
    const id = rubricId(row.id);
    if (ids.has(id)) fail("invalid_rubric");
    ids.add(id);
    const result = {
      id,
      description: boundedText(row.description, 4000, "invalid_rubric"),
      long_description: boundedText(
        row.long_description,
        12000,
        "invalid_rubric",
      ),
      points: decimal(row.points, true),
    };
    if (!ratings)
      Object.assign(result, {
        ratings: rubricRows(row.ratings, true, missing),
        criterion_use_range: nullableBoolean(
          row.criterion_use_range,
          "invalid_rubric",
        ),
        ignore_for_scoring: nullableBoolean(
          row.ignore_for_scoring,
          "invalid_rubric",
        ),
        learning_outcome_id:
          row.learning_outcome_id == null
            ? null
            : rubricId(row.learning_outcome_id),
        vendor_guid: boundedText(row.vendor_guid, 256, "invalid_rubric"),
      });
    return result;
  });
}

export function mapAssignmentObservation(raw, options) {
  if (!object(raw) || !object(options)) fail("invalid_assignment");
  if (
    Object.keys(options).some(
      (key) => !["courseId", "dateContext", "extracted"].includes(key),
    )
  )
    fail("invalid_assignment");
  const course = providerId(raw.course_id);
  const id = providerId(raw.id);
  if (providerId(options.courseId) !== course) fail("course_mismatch");
  const extracted = options.extracted;
  if (
    !object(extracted) ||
    Object.keys(extracted).some(
      (key) =>
        !["courseId", "assignmentId", "text", "coverage", "missing"].includes(
          key,
        ),
    )
  )
    fail("invalid_extraction");
  if (
    providerId(extracted.courseId) !== course ||
    providerId(extracted.assignmentId) !== id
  )
    fail("content_binding_mismatch");
  const content = boundedText(extracted.text, 24000, "segment_required", false);
  if (
    !COVERAGE.has(extracted.coverage) ||
    !Array.isArray(extracted.missing) ||
    extracted.missing.length > 50 ||
    extracted.missing.some(
      (reason) =>
        typeof reason !== "string" ||
        !/^[a-z0-9][a-z0-9_.:-]{0,127}$/.test(reason),
    )
  )
    fail("invalid_extraction");
  const missing = [...extracted.missing];
  const context = options.dateContext ?? "unverified";
  if (!["requesting_student", "unverified"].includes(context))
    fail("invalid_assignment");
  const fields = {};
  for (const key of ["due_at", "unlock_at", "lock_at"]) {
    fields[key] = context === "requesting_student" ? (raw[key] ?? null) : null;
    if (context === "requesting_student" && raw[key] === undefined)
      missing.push(key + "_not_observed");
  }
  if (context === "unverified")
    missing.push("student_specific_dates_unverified");
  fields.points_possible = decimal(raw.points_possible);
  if (raw.points_possible === undefined)
    missing.push("points_possible_not_observed");
  if (raw.submission_types == null) {
    fields.submission_types = null;
    missing.push("submission_types_not_observed");
  } else {
    if (
      !Array.isArray(raw.submission_types) ||
      raw.submission_types.length > 50 ||
      raw.submission_types.some(
        (type) => typeof type !== "string" || !/^[a-z_]{1,64}$/.test(type),
      )
    )
      fail("invalid_assignment");
    fields.submission_types = [...new Set(raw.submission_types)].sort();
  }
  fields.rubric = rubricRows(raw.rubric, false, missing);
  if (raw.rubric == null) missing.push("rubric_not_observed");
  fields.published = nullableBoolean(raw.published, "invalid_assignment");
  if (raw.published == null) missing.push("published_not_observed");
  nullableBoolean(raw.locked_for_user, "invalid_assignment");
  // These provider constraints are meaningful but absent from the agreed v1
  // fields. Preserve a coverage gap until their mapping is reviewed; do not
  // imply the selected field set captured the entire assignment requirements.
  const extraConstraints =
    (raw.allowed_extensions != null &&
      (!Array.isArray(raw.allowed_extensions) ||
        raw.allowed_extensions.length > 0)) ||
    (raw.allowed_attempts != null && raw.allowed_attempts !== -1) ||
    (raw.rubric_settings != null &&
      (!object(raw.rubric_settings) ||
        Object.keys(raw.rubric_settings).length > 0)) ||
    (raw.peer_reviews != null && raw.peer_reviews !== false) ||
    raw.group_category_id != null ||
    (raw.grading_type != null && raw.grading_type !== "points") ||
    fields.submission_types?.includes("external_tool");
  if (extraConstraints) missing.push("assignment_constraints_unmapped");
  let coverage = extracted.coverage;
  if (coverage === "complete" && missing.length) coverage = "partial";
  if (raw.locked_for_user === true) {
    coverage = "restricted";
    missing.push("assignment_locked");
  }
  const payload = {
    digest_version: 1,
    kind: "assignment",
    title: boundedText(raw.name, 500, "invalid_assignment", false),
    content,
    fields,
    coverage,
    missing,
  };
  let digestPayload;
  try {
    digestPayload = JSON.parse(
      new TextDecoder().decode(canonicalSourceBytes(payload)),
    );
  } catch {
    fail("invalid_digest_payload");
  }
  return {
    providerIdentity: { course_id: course, provider_id: id },
    digestPayload,
  };
}
