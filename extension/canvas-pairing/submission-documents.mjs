// Read-only own-submission content/status and grade projections, never quiz attempts.
import { canvasDecimal } from "../canvas/assignment-observation.mjs";
const normalize = (x) => x.replace(/\r\n?/g, "\n").normalize("NFC");
function text(value, limit = 1024) {
  if (value == null) return null;
  if (
    typeof value !== "string" ||
    /[\u0000\uD800-\uDFFF]/u.test(value) ||
    [...normalize(value)].length > limit
  )
    throw Error();
  return normalize(value);
}
function boolean(value) {
  if (value == null) return null;
  if (typeof value !== "boolean") throw Error();
  return value;
}
export function prepareSubmissionDocuments({ resource_key, page, origin }) {
  const [course, resource] = resource_key.split("/");
  if (
    !["grades", "submissions"].includes(resource) ||
    !Array.isArray(page.data) ||
    page.data.length > 4
  )
    throw Error();
  const documents = page.data.map((raw) => {
    const provider_id = String(raw.assignment_id);
    if (
      !/^[1-9][0-9]{0,19}$/.test(provider_id) ||
      !raw.assignment ||
      String(raw.assignment.id) !== provider_id ||
      String(raw.assignment.course_id) !== course
    )
      throw Error();
    const missing = [];
    const field = (name, convert = text) => {
      if (!Object.hasOwn(raw, name)) missing.push(name + "_not_observed");
      return convert(raw[name]);
    };
    let fields, kind, contents;
    if (resource === "submissions") {
      kind = "submission";
      fields = {
        assignment_id: provider_id,
        submitted_at: field("submitted_at"),
        workflow_state: field("workflow_state"),
        attempt: field("attempt", (x) => {
          if (x == null) return null;
          if (!Number.isSafeInteger(x) || x < 0 || x > 1000000) throw Error();
          return x;
        }),
        late: field("late", boolean),
        missing: field("missing", boolean),
      };
      const extracted = raw._wrytely_submission;
      if (extracted && !raw.assignment.quiz_id) {
        const body = text(extracted.text, 200000);
        missing.push(...extracted.missing);
        const comments = raw.submission_comments;
        if (!Array.isArray(comments) || comments.length > 1000) throw Error();
        const feedback = comments.map((comment) => {
          if (!comment || typeof comment !== "object" || Array.isArray(comment))
            throw Error();
          if ((comment.attachments?.length ?? 0) > 0 || comment.media_comment)
            missing.push("feedback_attachment_unread");
          return {
            text: text(comment.comment, 20000),
            created_at: text(comment.created_at),
          };
        });
        contents = { ...fields, body, feedback };
        if ((raw.attachments?.length ?? 0) > 0)
          missing.push("submission_attachment_unread");
        if (raw.url) missing.push("external_submission_unread");
      } else
        missing.push(
          "submission_body_unread",
          "submission_feedback_unread",
          ...(raw.assignment.quiz_id ? ["quiz_attempt_not_opened"] : []),
        );
    } else {
      kind = "grade";
      fields = {
        assignment_id: provider_id,
        score: field("score", (x) => canvasDecimal(x, true)),
        points_possible: canvasDecimal(raw.assignment.points_possible),
        grading_type: text(raw.assignment.grading_type),
        grade: field("grade"),
        grade_basis:
          raw.grade_matches_current_submission === true
            ? "provider_reported_current_attempt"
            : raw.grade_matches_current_submission === false
              ? "provider_reported_previous_attempt"
              : "provider_reported_attempt_unverified",
      };
      for (const name of ["points_possible", "grading_type"])
        if (!Object.hasOwn(raw.assignment, name))
          missing.push(name + "_not_observed");
      if (raw.grade_matches_current_submission == null)
        missing.push("grade_attempt_not_verified");
      else boolean(raw.grade_matches_current_submission);
      if (raw.excused === true) missing.push("assignment_excused");
      else if (raw.excused == null) missing.push("excusal_not_observed");
      else boolean(raw.excused);
      if (raw.assignment_visible === false)
        missing.push("assignment_no_longer_visible");
      else if (raw.assignment_visible == null)
        missing.push("assignment_visibility_not_observed");
      else boolean(raw.assignment_visible);
      missing.push("course_total_not_collected", "grading_policy_unread");
    }
    const title = text(raw.assignment.name, 270);
    if (!title?.trim()) throw Error();
    // Explicit data-only JSON; user/author IDs, credentials and download URLs omitted.
    return {
      owner_object: { kind, provider_id },
      object_fields: fields,
      metadata: {
        title: `${title}: ${kind === "grade" ? "grade" : "submission"}`,
        format: "text",
        extractor_version: "canvas.json.v1",
        provider_updated_at: raw.updated_at ?? null,
        coverage: missing.length ? "partial" : "complete",
        missing: [...new Set(missing)].sort(),
      },
      source: { text: JSON.stringify(contents ?? fields, null, 2) },
      reference: `${origin}/courses/${course}/assignments/${provider_id}`,
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
