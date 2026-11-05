// Private worker helpers. No scheduler, independent storage or credential export.
import { canonicalSourceBytes } from "../canvas/source-digest.mjs";
import { checkedOrigin } from "../canvas-feasibility/probe.mjs";

const enrollmentStates = new Set([
  "active",
  "invited",
  "completed",
  "inactive",
  "rejected",
  "creation_pending",
  "deleted",
]);
const providerErrors = new Set([
  "invalid_course_page",
  "invalid_provider_id",
  "unsafe_pagination",
  "pagination_cycle",
  "invalid_pagination",
  "invalid_collection",
  "invalid_response",
  "invalid_json",
  "size_limit",
  "login_required",
  "permission_denied",
  "not_found",
  "rate_limited",
  "provider_unavailable",
  "provider_error",
  "login_or_non_json",
  "network_or_redirect_blocked",
  "canvas_session_unavailable",
  "canvas_account_changed",
  "reconnect_required",
  "storage_unavailable",
  "storage_cleanup_required",
  "invalid_discovery_input",
  "discovery_outcome_unknown",
  "discovery_reconciliation_required",
  "discovery_context_changed",
  "discovery_not_active",
  "discovery_request_rejected",
  "discovery_identity_required",
  "invalid_assignment_input",
  "assignment_extraction_invalid",
]);
export const RECOVERY_DIAGNOSTIC_CODES = Object.freeze([
  ...[
    "inspect",
    "begin",
    "recover",
    "resume",
    "finish",
    "close_courses",
    "page",
    "verify",
  ].map((stage) => `course_${stage}_failed`),
  ...["inspect", "close_assignments", "assignment_page", "verify"].map(
    (stage) => `assignment_${stage}_failed`,
  ),
]);
const text = (value) => {
  if (typeof value !== "string" || /[\u0000\uD800-\uDFFF]/u.test(value))
    return null;
  const normalized = value.replace(/\r\n?/g, "\n").normalize("NFC");
  return normalized.trim() && [...normalized].length <= 500 ? normalized : null;
};

export function mapCoursePage(page, originValue, observed_at) {
  try {
    const origin = checkedOrigin(originValue);
    if (!Array.isArray(page.data) || page.data.length > 50) throw Error();
    const ids = new Set();
    const items = page.data.map((row) => {
      if (
        !row ||
        typeof row !== "object" ||
        Array.isArray(row) ||
        !["string", "number"].includes(typeof row.id) ||
        (typeof row.id === "number" && !Number.isSafeInteger(row.id)) ||
        !/^[1-9][0-9]{0,19}$/.test(String(row.id)) ||
        ids.has(String(row.id))
      )
        throw Error();
      const provider_id = String(row.id);
      ids.add(provider_id);
      const missing = [];
      const field = (name, value) => {
        const result = text(value);
        if (result === null) missing.push(name);
        return result;
      };
      const title = field("title", row.name) ?? "";
      const course_code = field("course_code", row.course_code);
      const timezone = field("timezone", row.time_zone);
      const enrollments = row.enrollments;
      const states = Array.isArray(enrollments)
        ? enrollments.map((e) => e?.enrollment_state)
        : [];
      const state =
        states.length &&
        states.every((s) => enrollmentStates.has(s)) &&
        new Set(states).size === 1
          ? states[0]
          : null;
      const enrollment_state = field("enrollment_state", state);
      const payload = JSON.parse(
        new TextDecoder().decode(
          canonicalSourceBytes({
            digest_version: 1,
            kind: "course",
            title,
            content: "",
            fields: { course_code, timezone, enrollment_state },
            coverage: missing.length ? "partial" : "complete",
            missing,
          }),
        ),
      );
      return {
        provider_id,
        provider_updated_at: null,
        title: payload.title,
        reference: `${origin}/courses/${provider_id}`,
        content: "",
        fields: payload.fields,
        coverage: payload.coverage,
        missing: payload.missing,
      };
    });
    return {
      items,
      observed_at,
      next_cursor: page.next_cursor,
      coverage:
        page.next_cursor !== null
          ? { state: "partial", reason: "more_pages" }
          : items.some((item) => item.coverage !== "complete")
            ? { state: "partial", reason: "extraction_failed" }
            : { state: "complete", reason: null },
    };
  } catch {
    const error = Error("invalid_course_page");
    error.code = "invalid_course_page";
    throw error;
  }
}

function summary(value, state, action = null) {
  return {
    state,
    action,
    generation: value.generation ?? null,
    scope_revision: value.scope_revision ?? null,
    seen_count: value.seen_count ?? 0,
    open_resources: value.open_resources ?? 0,
    coverage: value.coverage ?? null,
  };
}

export async function collectCourseTick({
  operations,
  inspect,
  readPage,
  origin,
  conflicts,
}) {
  let current,
    action = "inspect",
    verifying = false;
  try {
    current = await inspect();
    if (current.state === "idle") {
      action = "begin";
      await operations.beginDiscovery();
    } else if (current.state === "finished")
      return summary(current, "finished");
    // An accepted receipt can outlive its writer lease (especially final finish).
    // Replay that primary key before attempting a new lease on a terminal scan.
    else if (current.pending && current.pending !== "resume") {
      action = "recover";
      try {
        await operations.retryDiscovery();
      } catch (error) {
        if (
          !["discovery_lease_expired", "discovery_lease_replaced"].includes(
            error?.code,
          )
        )
          throw error;
        action = "resume";
        await operations.resumeDiscovery();
      }
    } else if (current.pending === "resume" || current.needs_resume) {
      action = "resume";
      await operations.resumeDiscovery();
    } else if (current.courses_closed) {
      if (current.open_resources) return summary(current, "awaiting_resources");
      action = "finish";
      await operations.finishDiscovery();
    } else if (
      current.checkpoint.sequence > 0 &&
      current.checkpoint.next_cursor === null
    ) {
      action = "close_courses";
      const complete =
        current.last_page_coverage === "complete" && !current.incomplete;
      await operations.finishDiscoveryResource({
        resource_key: "courses",
        outcome: complete ? "complete" : "partial",
        reason: complete ? null : "extraction_failed",
      });
    } else {
      action = "page";
      const page = await readPage(current.checkpoint.next_cursor);
      await operations.commitDiscoveryPage(
        mapCoursePage(page, origin, new Date().toISOString()),
      );
    }
    verifying = true;
    current = await inspect();
    return summary(
      current,
      current.state === "finished" ? "finished" : "progress",
      action,
    );
  } catch (error) {
    const code = error?.code;
    return {
      state: "blocked",
      reason:
        providerErrors.has(code) ||
        conflicts.some((c) => code === `discovery_${c}`)
          ? code
          : `course_${verifying ? "verify" : action}_failed`,
    };
  }
}

export async function collectAssignmentTick({
  operations,
  inspect,
  courseTick,
  readPage,
  extractPage,
  conflicts,
}) {
  let stage = "inspect";
  try {
    let current = await inspect();
    if (
      current.state !== "active" ||
      current.pending ||
      current.needs_resume ||
      !current.courses_closed
    )
      return courseTick();
    const active = current.academic;
    const resource =
      active && current.open_keys.includes(active.resource_key)
        ? active.resource_key
        : current.open_keys.find((key) =>
            /^[1-9][0-9]{0,19}\/assignments$/.test(key),
          );
    if (!resource) return courseTick();
    const course = resource.split("/")[0];
    if (!current.selected_courses.includes(course)) {
      const error = Error("discovery_resource_not_selected");
      error.code = "discovery_resource_not_selected";
      throw error;
    }
    let action;
    if (
      active?.resource_key === resource &&
      current.checkpoint.next_cursor === null
    ) {
      action = stage = "close_assignments";
      const complete =
        active.last_page_coverage === "complete" && !active.incomplete;
      await operations.finishAssignmentResource({
        resource_key: resource,
        outcome: complete ? "complete" : "partial",
        reason: complete ? null : "extraction_failed",
      });
    } else {
      action = stage = "assignment_page";
      if (
        current.checkpoint.sequence >= 10000 ||
        (active?.resource_key === resource &&
          (active.page_count >= 100 || active.seen_count >= 5000))
      ) {
        const error = Error("invalid_assignment_input");
        error.code = "invalid_assignment_input";
        throw error;
      }
      const page = await readPage(
        course,
        active?.resource_key === resource
          ? current.checkpoint.next_cursor
          : null,
      );
      const observed_at = new Date().toISOString();
      const items = await extractPage(course, page.data);
      await operations.commitAssignmentPage({
        resource_key: resource,
        observed_at,
        next_cursor: page.next_cursor,
        coverage: {
          state: page.next_cursor ? "partial" : "complete",
          reason: page.next_cursor ? "more_pages" : null,
        },
        items,
      });
    }
    stage = "verify";
    current = await inspect();
    return summary(current, "progress", action);
  } catch (error) {
    const code = error?.code;
    return {
      state: "blocked",
      reason:
        providerErrors.has(code) ||
        conflicts.some((c) => code === `discovery_${c}`)
          ? code
          : `assignment_${stage}_failed`,
    };
  }
}
