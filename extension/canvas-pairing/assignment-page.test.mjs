import assert from "node:assert/strict";
import test from "node:test";
import {
  prepareAssignmentPage,
  validateAssignmentPage,
} from "./assignment-page.mjs";

const origin = "https://canvas.example.edu";
const now = "2026-11-01T00:00:00Z";
const date = (x) => typeof x === "string" && Number.isFinite(Date.parse(x));
const input = () => ({
  resource_key: "101/assignments",
  observed_at: now,
  next_cursor: null,
  coverage: { state: "complete", reason: null },
  items: [
    {
      raw: {
        id: 17,
        course_id: 101,
        name: "Synthetic assignment",
        due_at: null,
        unlock_at: null,
        lock_at: null,
        points_possible: 20,
        submission_types: ["online_upload"],
        rubric: [],
        published: true,
        description: "PRIVATE_RAW_BODY",
      },
      extracted: {
        courseId: 101,
        assignmentId: 17,
        text: "Synthetic extracted text",
        coverage: "complete",
        missing: [],
      },
      dateContext: "requesting_student",
    },
  ],
});

test("reuses mapper and emits only exact bound C2 assignment wire", () => {
  const value = prepareAssignmentPage(input(), origin, date);
  assert.equal(value.items[0].provider_id, "17");
  assert.equal(value.items[0].kind, "assignment");
  assert.equal(
    value.items[0].reference,
    origin + "/courses/101/assignments/17",
  );
  assert.equal(value.items[0].fields.points_possible, "20");
  assert.equal(value.coverage.state, "complete");
  assert.ok(!JSON.stringify(value).includes("PRIVATE"));
  assert.doesNotThrow(() => validateAssignmentPage(value, origin, date));
});

for (const change of [
  "course",
  "extracted",
  "resource",
  "title",
  "content",
  "unknown",
]) {
  test(`rejects invalid assignment binding/shape/limit: ${change}`, () => {
    const value = input();
    if (change === "course") value.items[0].raw.course_id = 102;
    if (change === "extracted") value.items[0].extracted.assignmentId = 18;
    if (change === "resource") value.resource_key = "101/grades";
    if (change === "title") value.items[0].raw.name = "\u0344".repeat(151);
    if (change === "content")
      value.items[0].extracted.text = "\u0344".repeat(12001);
    if (change === "unknown") value.owner_id = "untrusted";
    assert.throws(
      () => prepareAssignmentPage(value, origin, date),
      /invalid_assignment_input/,
    );
  });
}

test("unknown student date context remains an explicit partial gap", () => {
  const value = input();
  delete value.items[0].dateContext;
  const result = prepareAssignmentPage(value, origin, date);
  assert.equal(result.coverage.state, "partial");
  assert.ok(
    result.items[0].missing.includes("student_specific_dates_unverified"),
  );
});

test("partial items on a nonterminal page retain more_pages coverage", () => {
  const value = input();
  value.items[0].raw.rubric = null;
  value.next_cursor = "PRIVATE_CURSOR";
  value.coverage = { state: "partial", reason: "more_pages" };
  const result = prepareAssignmentPage(value, origin, date);
  assert.equal(result.items[0].coverage, "partial");
  assert.deepEqual(result.coverage, { state: "partial", reason: "more_pages" });
});

test("duplicate provider IDs and oversized input cannot create a page", () => {
  const value = input();
  value.items.push(structuredClone(value.items[0]));
  assert.throws(
    () => prepareAssignmentPage(value, origin, date),
    /invalid_assignment_input/,
  );
  const huge = input();
  huge.items[0].raw.description = "x".repeat(2 * 1024 * 1024);
  assert.throws(
    () => prepareAssignmentPage(huge, origin, date),
    /invalid_assignment_input/,
  );
});

for (const change of [
  "reference",
  "fields",
  "title",
  "coverage",
  "extra",
  "kind",
]) {
  test(`persisted wire validation refuses corruption: ${change}`, () => {
    const value = prepareAssignmentPage(input(), origin, date),
      item = value.items[0];
    if (change === "reference") item.reference = "https://evil.example/";
    if (change === "fields") item.fields.owner_id = "untrusted";
    if (change === "title") item.title = "\ud800";
    if (change === "coverage") {
      item.fields.rubric = null;
      item.coverage = "complete";
    }
    if (change === "extra") item.secret = "untrusted";
    if (change === "kind") item.kind = "grade";
    assert.throws(() => validateAssignmentPage(value, origin, date));
  });
}
