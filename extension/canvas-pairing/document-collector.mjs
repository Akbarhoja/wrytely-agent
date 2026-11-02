// One durable connector step. No independent scheduler, journal or raw-body cache.
import { mapAssignmentObservation } from "../canvas/assignment-observation.mjs";

const supported = (key) =>
  /^[1-9][0-9]{0,19}\/(assignments|syllabus|pages)$/.test(key);
const controlled = new Set([
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
]);
const summary = (s, action) => ({
  state: "progress",
  action,
  seen_count: s.seen_count ?? 0,
  coverage: s.coverage ?? null,
});
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
}) {
  const [course, kind] = resource_key.split("/");
  if (
    !supported(resource_key) ||
    !Array.isArray(page.data) ||
    page.data.length > 4
  )
    throw Error();
  const inputs = page.data.map((raw) => {
    const provider_id = String(
      kind === "assignments" ? raw.id : kind === "pages" ? raw.page_id : course,
    );
    const html =
      kind === "assignments"
        ? raw.description
        : kind === "pages"
          ? raw.body
          : raw.syllabus_body;
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
    if (kind === "assignments") {
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
          kind === "assignments"
            ? "assignment"
            : kind === "pages"
              ? "page"
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
  origin,
  conflicts,
}) {
  try {
    let current = await inspect();
    if (
      current.state !== "active" ||
      current.pending ||
      current.needs_resume ||
      !current.courses_closed
    )
      return operations.collectCoursePage();
    if (current.document_active) {
      await operations.continueDocumentPage();
      return summary(await inspect(), "document_step");
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
      await operations.finishDocumentResource({
        resource_key: resource,
        outcome: complete ? "complete" : "partial",
        reason: complete ? null : "extraction_failed",
      });
      return summary(await inspect(), "close_documents");
    }
    if (
      current.checkpoint.sequence >= 10000 ||
      (current.academic?.resource_key === resource &&
        (current.academic.page_count >= 100 ||
          current.academic.seen_count >= 5000))
    )
      throw Object.assign(Error(), { code: "size_limit" });
    const page = await readPage(
      course,
      kind,
      current.academic?.resource_key === resource
        ? current.checkpoint.next_cursor
        : null,
    );
    const input = await prepareCollectedDocuments({
      resource_key: resource,
      page,
      origin,
      extract,
    });
    await operations.commitDocumentPage(input);
    current = await inspect();
    return summary(current, "document_page");
  } catch (e) {
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
