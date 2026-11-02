import assert from "node:assert/strict";
import test from "node:test";
import { prepareSubmissionDocuments } from "./submission-documents.mjs";
import { makeDocumentReader } from "./document-reader.mjs";
const origin = "https://canvas.example.edu";
const raw = () => ({
  assignment_id: 17,
  user_id: 7,
  assignment: {
    id: 17,
    course_id: 101,
    name: "Quiz or homework",
    points_possible: 20,
    grading_type: "points",
    quiz_id: 80,
  },
  submitted_at: null,
  workflow_state: "unsubmitted",
  attempt: 0,
  late: false,
  missing: true,
  score: null,
  grade: null,
  body: "PRIVATE_BODY",
  submission_comments: ["PRIVATE_FEEDBACK"],
});
function prepare(kind, value = raw()) {
  return prepareSubmissionDocuments({
    origin,
    resource_key: `101/${kind}`,
    page: { data: [value], next_cursor: null },
  }).documents[0];
}
test("ungraded means unknown, never zero or a guessed course average", () => {
  const grade = prepare("grades");
  assert.equal(grade.object_fields.score, null);
  assert.equal(grade.object_fields.grade, null);
  assert.equal(grade.object_fields.points_possible, "20");
  assert.equal(
    grade.object_fields.grade_basis,
    "provider_reported_attempt_unverified",
  );
  assert.ok(grade.metadata.missing.includes("course_total_not_collected"));
  assert.equal(grade.metadata.coverage, "partial");
});
test("canonical grade decimals and negative marks reuse the existing mapper", () => {
  const value = raw();
  value.score = -0.5;
  value.grade = "-0.5";
  assert.equal(prepare("grades", value).object_fields.score, "-0.5");
});

test("a resubmission's previous-attempt mark is not described as current", () => {
  const value = raw();
  value.grade_matches_current_submission = false;
  value.score = 12;
  value.grade = "12";
  const document = prepare("grades", value);
  assert.equal(
    document.object_fields.grade_basis,
    "provider_reported_previous_attempt",
  );
  assert.equal(document.object_fields.score, "12");
});
test("grade attempt, excusal and assignment visibility remain explicit", () => {
  const value = raw();
  value.grade_matches_current_submission = true;
  value.excused = true;
  value.assignment_visible = false;
  const document = prepare("grades", value);
  assert.equal(
    document.object_fields.grade_basis,
    "provider_reported_current_attempt",
  );
  assert.ok(document.metadata.missing.includes("assignment_excused"));
  assert.ok(document.metadata.missing.includes("assignment_no_longer_visible"));
  assert.equal(document.metadata.coverage, "partial");
  assert.ok(
    prepare("grades").metadata.missing.includes("grade_attempt_not_verified"),
  );
});
test("submission projection retains exact status and omits uncollected body/feedback", () => {
  const document = prepare("submissions");
  assert.deepEqual(document.object_fields, {
    assignment_id: "17",
    submitted_at: null,
    workflow_state: "unsubmitted",
    attempt: 0,
    late: false,
    missing: true,
  });
  const payload = JSON.stringify(document);
  for (const secret of [
    "PRIVATE_BODY",
    "PRIVATE_FEEDBACK",
    "user_id",
    "quiz_id",
  ])
    assert.ok(!payload.includes(secret));
  assert.deepEqual(JSON.parse(document.source.text), document.object_fields);
  assert.ok(document.metadata.missing.includes("submission_body_unread"));
});
test("missing provider flags stay unknown instead of false", () => {
  const value = raw();
  delete value.late;
  delete value.missing;
  const document = prepare("submissions", value);
  assert.equal(document.object_fields.late, null);
  assert.equal(document.object_fields.missing, null);
  assert.ok(document.metadata.missing.includes("late_not_observed"));
});
for (const [name, value] of [
  ["attempt", true],
  ["attempt", -1],
  ["attempt", 1000001],
  ["late", "false"],
  ["missing", 1],
]) {
  test(`rejects invalid submission ${name}=${value}`, () => {
    const input = raw();
    input[name] = value;
    assert.throws(() => prepare("submissions", input));
  });
}
for (const kind of ["submissions", "grades"]) {
  test(`reads only current student's ${kind} and never opens a quiz attempt`, async () => {
    const calls = [];
    const reader = makeDocumentReader(origin, async (url, init) => {
      calls.push(url);
      assert.equal(init.method, "GET");
      assert.ok(
        !url.includes("quizzes") &&
          !url.includes("/take") &&
          !url.includes("quiz_submissions"),
      );
      const response = Response.json(
        url.endsWith("/profile") ? { id: 7 } : [raw()],
      );
      Object.defineProperty(response, "url", { value: url });
      return response;
    });
    const page = await reader("101", kind, null, "7");
    assert.equal(page.data[0].user_id, 7);
    assert.deepEqual(
      calls.filter((x) => !x.endsWith("/profile")),
      [
        origin +
          "/api/v1/courses/101/students/submissions?per_page=4&include[]=assignment",
      ],
    );
  });
  test(`rejects another student's ${kind} even if Canvas returns it`, async () => {
    const value = raw();
    value.user_id = 8;
    const reader = makeDocumentReader(origin, async (url) => {
      const response = Response.json(
        url.endsWith("/profile") ? { id: 7 } : [value],
      );
      Object.defineProperty(response, "url", { value: url });
      return response;
    });
    await assert.rejects(reader("101", kind, null, "7"), /invalid_collection/);
  });
}
test("status pagination cannot request all students or navigate into a quiz", async () => {
  const reader = makeDocumentReader(origin, async () =>
    assert.fail("unsafe cursor fetched"),
  );
  for (const cursor of [
    origin +
      "/api/v1/courses/101/students/submissions?per_page=4&include[]=assignment&student_ids[]=all",
    origin +
      "/api/v1/courses/101/quizzes/80/submissions?per_page=4&include[]=assignment",
  ])
    await assert.rejects(
      reader("101", "grades", cursor, "7"),
      /unsafe_pagination/,
    );
});

test("status reads preserve safe next-page cursors and validate each returned page", async () => {
  const next =
    origin +
    "/api/v1/courses/101/students/submissions?per_page=4&include[]=assignment&page=next-A";
  let current = 0;
  const reader = makeDocumentReader(origin, async (url) => {
    if (url.endsWith("/profile")) {
      const response = Response.json({ id: 7 });
      Object.defineProperty(response, "url", { value: url });
      return response;
    }
    current++;
    const response = Response.json([raw()], {
      headers: current === 1 ? { link: `<${next}>; rel="next"` } : {},
    });
    Object.defineProperty(response, "url", { value: url });
    return response;
  });
  const first = await reader("101", "grades", null, "7");
  assert.equal(first.next_cursor, next);
  const second = await reader("101", "grades", first.next_cursor, "7");
  assert.equal(second.next_cursor, null);
  assert.equal(current, 2);
});
test("status rows must have an assignment from the selected course", async () => {
  const value = raw();
  value.assignment.course_id = 102;
  const reader = makeDocumentReader(origin, async (url) => {
    const response = Response.json(
      url.endsWith("/profile") ? { id: 7 } : [value],
    );
    Object.defineProperty(response, "url", { value: url });
    return response;
  });
  await assert.rejects(
    reader("101", "submissions", null, "7"),
    /invalid_collection/,
  );
});
test("malformed grade attempt flags cannot certify current marks", () => {
  const value = raw();
  value.grade_matches_current_submission = "true";
  assert.throws(() => prepare("grades", value));
});
