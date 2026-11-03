// One durable connector step. No independent scheduler, journal or raw-body cache.
import { prepareSubmissionDocuments } from "./submission-documents.mjs";
import { mapAssignmentObservation } from "../canvas/assignment-observation.mjs";

import { prepareModuleDocuments } from "./module-reader.mjs";
import { prepareFileDocuments } from "./file-documents.mjs";
const supported = (key) =>
  /^[1-9][0-9]{0,19}\/(assignments|syllabus|pages|announcements|discussions|submissions|grades|modules|files)$/.test(
    key,
  );
export const DOCUMENT_COLLECTION_ERRORS = Object.freeze([
  "login_required",
  "permission_denied",
  "rate_limited",
  "provider_unavailable",
  "network_or_redirect_blocked",
  "canvas_account_changed",
  "reconnect_required",
  "canvas_session_unavailable",
  "discovery_outcome_unknown",
  "discovery_context_changed",
  "discovery_journal_invalid",
  "invalid_document_input",
  "invalid_collection",
  "unsafe_pagination",
  "pagination_cycle",
  "invalid_pagination",
  "invalid_provider_id",
  "size_limit",
  "login_or_non_json",
  "invalid_response",
  "provider_error",
  "file_network_failed",
  "file_access_failed",
  "unsafe_file_url",
  "unsafe_file_redirect",
]);
const controlled = new Set(DOCUMENT_COLLECTION_ERRORS);
const summary = (s, action) => ({
  state: "progress",
  action,
  seen_count: s.seen_count ?? 0,
  coverage: s.coverage ?? null,
});
function postedTimestamp(value) {
  if (value == null) return null;
  if (typeof value !== "string") throw Error();
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/.exec(
      value,
    );
  if (!match) throw Error();
  const [, y, m, d, h, min, sec, fraction = "", zone] = match;
  const [year, month, day, hour, minute, second] = [y, m, d, h, min, sec].map(
    Number,
  );
  const days = [
    31,
    year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28,
    31,
    30,
    31,
    30,
    31,
    31,
    30,
    31,
    30,
    31,
  ];
  if (
    year < 1 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > days[month - 1] ||
    hour > 23 ||
    minute > 59 ||
    second > 59 ||
    (zone !== "Z" &&
      (Number(zone.slice(1, 3)) > 23 || Number(zone.slice(4)) > 59))
  )
    throw Error();
  return new Date(value)
    .toISOString()
    .replace(/\.\d{3}Z$/, "." + fraction.padEnd(6, "0") + "Z");
}
const normal = (s) => s.replace(/\r\n?/g, "\n").normalize("NFC");
function validText(x, max) {
  if (
    typeof x !== "string" ||
    /[\u0000\uD800-\uDFFF]/u.test(x) ||
    [...normal(x)].length > max
  )
    throw Error();
  return normal(x);
}

export async function prepareCollectedDocuments({
  resource_key,
  page,
  origin,
  extract,
  extractFile,
}) {
  const [course, kind] = resource_key.split("/");
  if (
    !supported(resource_key) ||
    !Array.isArray(page.data) ||
    page.data.length > 4
  )
    throw Error();
  if (kind === "files")
    return prepareFileDocuments({ resource_key, page, origin, extractFile });
  if (kind === "modules")
    return prepareModuleDocuments({ resource_key, page, origin });
  if (["submissions", "grades"].includes(kind)) {
    if (kind === "submissions") {
      const inputs = page.data
        .filter((raw) => !raw.assignment?.quiz_id)
        .map((raw) => ({
          provider_id: String(raw.assignment_id),
          html: raw.body ?? null,
        }));
      const extracted = inputs.length
        ? await extract(course, kind, inputs)
        : null;
      if (
        inputs.length &&
        (extracted?.schema_version !== 2 ||
          extracted.extractor_version !== "canvas.html.v1" ||
          extracted.resource?.course_id !== course ||
          extracted.resource?.kind !== kind ||
          extracted.items?.length !== inputs.length)
      )
        throw Error();
      page = {
        ...page,
        data: page.data.map((raw) => {
          if (raw.assignment?.quiz_id)
            return { ...raw, _wrytely_submission: null };
          const item = extracted.items.find(
            (item) => item.provider_id === String(raw.assignment_id),
          );
          if (
            !item ||
            typeof item.text !== "string" ||
            !Array.isArray(item.missing)
          )
            throw Error();
          return { ...raw, _wrytely_submission: item };
        }),
      };
    }
    return prepareSubmissionDocuments({ resource_key, page, origin });
  }
  const inputs = page.data.map((raw) => {
    const provider_id = String(
      kind === "syllabus" ? course : kind === "pages" ? raw.page_id : raw.id,
    );
    const html =
      kind === "assignments"
        ? raw.description
        : kind === "pages"
          ? raw.body
          : kind === "syllabus"
            ? raw.syllabus_body
            : raw.message;
    if (html != null && typeof html !== "string") throw Error();
    return {
      provider_id,
      html: raw.locked_for_user === true ? null : (html ?? null),
    };
  });
  const extracted = inputs.length ? await extract(course, kind, inputs) : null;
  if (
    inputs.length &&
    (extracted?.schema_version !== 2 ||
      extracted.extractor_version !== "canvas.html.v1" ||
      extracted.resource?.course_id !== course ||
      extracted.resource?.kind !== kind ||
      !Array.isArray(extracted.items) ||
      extracted.items.length !== inputs.length)
  )
    throw Error();
  const byId = new Map();
  for (const item of extracted?.items ?? []) {
    if (
      !item ||
      byId.has(item.provider_id) ||
      !inputs.some((i) => i.provider_id === item.provider_id) ||
      item.coverage !== "partial" ||
      !Array.isArray(item.missing) ||
      !item.missing.length ||
      item.missing.length > 50 ||
      item.missing.some(
        (x) =>
          typeof x !== "string" || !/^[a-z0-9][a-z0-9_.:-]{0,127}$/.test(x),
      )
    )
      throw Error();
    validText(item.text, 200000);
    if (
      inputs.find((i) => i.provider_id === item.provider_id).html === null &&
      item.text !== ""
    )
      throw Error();
    byId.set(item.provider_id, item);
  }
  const documents = page.data.map((raw, index) => {
    const provider_id = inputs[index].provider_id,
      extracted = byId.get(provider_id);
    let title,
      fields,
      coverage = extracted.coverage,
      missing = [...extracted.missing],
      reference;
    if (kind === "discussions" && raw._wrytely_entry) {
      title = `Discussion entry ${provider_id}`;
      fields = { ...raw._wrytely_entry, author_role: null, due_at: null };
      missing.push(
        "author_role_not_observed",
        "student_specific_dates_unverified",
      );
      if (raw.attachment || raw.attachments?.length)
        missing.push("entry_attachment_unread");
      reference = `${origin}/courses/${course}/discussion_topics/${fields.topic_id}#entry-${provider_id}`;
    } else if (kind === "assignments") {
      // Reuse the existing provider mapper for dates/rubrics/constraints. The full
      // body goes only through document segmentation, never its short-text field.
      const mapped = mapAssignmentObservation(raw, {
        courseId: course,
        dateContext: "requesting_student",
        extracted: {
          courseId: course,
          assignmentId: provider_id,
          text: "",
          coverage,
          missing,
        },
      }).digestPayload;
      ({ title, fields, coverage, missing } = mapped);
      reference = `${origin}/courses/${course}/assignments/${provider_id}`;
    } else if (["announcements", "discussions"].includes(kind)) {
      title = raw.title;
      reference = `${origin}/courses/${course}/discussion_topics/${provider_id}`;
      if (kind === "announcements") {
        fields = {
          author_role: null,
          posted_at: postedTimestamp(raw.posted_at),
          announcement_id: provider_id,
        };
        missing.push("author_role_not_observed");
        if (raw.discussion_subentry_count !== 0)
          missing.push("announcement_replies_unread");
      } else {
        fields = {
          topic_id: provider_id,
          parent_entry_id: null,
          author_role: null,
          required_initial_post:
            typeof raw.require_initial_post === "boolean"
              ? raw.require_initial_post
              : null,
          due_at: null,
        };
        missing.push(
          "discussion_replies_unread",
          "author_role_not_observed",
          "student_specific_dates_unverified",
        );
        if (
          raw.require_initial_post === true &&
          raw.user_can_see_posts !== true
        )
          missing.push("initial_post_required");
      }
      if (raw.locked_for_user === true) {
        coverage = "restricted";
        missing.push("content_locked");
      }
    } else {
      title =
        kind === "syllabus" ? `${raw.name ?? "Course"} syllabus` : raw.title;
      fields = {
        page_id: kind === "pages" ? provider_id : null,
        module_ids: null,
        source_format: "html",
      };
      missing.push("module_links_unread");
      reference = `${origin}/courses/${course}/${kind === "syllabus" ? "assignments/syllabus" : "pages/" + provider_id}`;
      if (raw.locked_for_user === true) {
        coverage = "restricted";
        missing.push("content_locked");
      }
    }
    return {
      owner_object: {
        kind:
          kind === "discussions" && raw._wrytely_entry
            ? "entry"
            : kind === "assignments"
              ? "assignment"
              : kind === "pages"
                ? "page"
                : kind === "announcements"
                  ? "announcement"
                  : kind === "discussions"
                    ? "discussion"
                    : "syllabus",
        provider_id,
      },
      object_fields: fields,
      metadata: {
        title: validText(title, 300),
        format: "html_text",
        extractor_version: "canvas.html.v1",
        provider_updated_at: raw.updated_at ?? null,
        coverage,
        missing: [...new Set(missing)].sort(),
      },
      source: { text: validText(extracted.text, 200000) },
      reference,
    };
  });
  return {
    resource_key,
    observed_at: new Date().toISOString(),
    documents,
    next_cursor: page.next_cursor,
    coverage: {
      state: page.next_cursor ? "partial" : "complete",
      reason: page.next_cursor ? "more_pages" : null,
    },
  };
}

export async function collectDocumentTick({
  operations,
  inspect,
  readPage,
  extract,
  extractFile,
  origin,
  conflicts,
}) {
  try {
    const current = await inspect();
    if (
      current.state !== "active" ||
      current.pending ||
      current.needs_resume ||
      !current.courses_closed
    )
      return operations.collectCoursePage();
    if (current.document_active) {
      // Existing journal operations already persist and run finalCheck (current
      // context + Canvas identity) before returning this projection. Reuse it
      // instead of making another context/profile round trip for display only.
      return summary(await operations.continueDocumentPage(), "document_step");
    }
    if (
      current.academic &&
      !current.document_journal &&
      current.open_keys.includes(current.academic.resource_key)
    )
      return operations.collectAssignmentPage(); // Resume pre-upgrade schema1 work unchanged.
    const resource =
      current.academic &&
      current.open_keys.includes(current.academic.resource_key)
        ? current.academic.resource_key
        : current.open_keys.find(supported);
    if (!resource || !supported(resource))
      return operations.collectAssignmentPage();
    const [course, kind] = resource.split("/");
    if (!current.selected_courses.includes(course))
      throw Object.assign(Error(), { code: "discovery_resource_not_selected" });
    if (
      current.academic?.resource_key === resource &&
      current.checkpoint.next_cursor === null
    ) {
      const complete =
        !current.academic.incomplete &&
        current.academic.last_page_coverage === "complete";
      const completed = await operations.finishDocumentResource({
        resource_key: resource,
        outcome: complete ? "complete" : "partial",
        reason: complete ? null : "extraction_failed",
      });
      return summary(completed, "close_documents");
    }
    if (
      current.checkpoint.sequence >= 10000 ||
      (current.academic?.resource_key === resource &&
        (current.academic.page_count >= 100 ||
          current.academic.seen_count >= 5000))
    )
      throw Object.assign(Error(), { code: "size_limit" });
    let page;
    try {
      page = await readPage(
        course,
        kind,
        current.academic?.resource_key === resource
          ? current.checkpoint.next_cursor
          : null,
      );
    } catch (error) {
      if (!["permission_denied", "not_found"].includes(error?.code))
        throw error;
      // Only this selected resource is unavailable. Persist the gap so other
      // courses can continue; no missing page becomes deletion or complete data.
      const completed = await operations.finishDiscoveryResource({
        resource_key: resource,
        outcome: error.code === "permission_denied" ? "restricted" : "partial",
        reason:
          error.code === "permission_denied"
            ? "permission_denied"
            : "extraction_failed",
      });
      return summary(completed, "restricted_documents");
    }
    const input = await prepareCollectedDocuments({
      resource_key: resource,
      page,
      origin,
      extract,
      extractFile,
    });
    return summary(await operations.commitDocumentPage(input), "document_page");
  } catch (e) {
    // A bounded provider read/extraction can outlive the lease inspected at the
    // start of this tick. Re-enter the existing pending-first recovery path;
    // it replays accepted receipts before renewing the writer lease. Never
    // treat a replaced lease (another writer) as permission to continue here.
    if (e?.code === "discovery_lease_expired")
      return operations.collectCoursePage();
    return {
      state: "blocked",
      reason:
        controlled.has(e?.code) ||
        conflicts.some((x) => e?.code === `discovery_${x}`)
          ? e.code
          : "collector_failed",
    };
  }
}
