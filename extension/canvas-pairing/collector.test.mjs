import test from "node:test";
import assert from "node:assert/strict";
import {
  mapCoursePage,
  collectCourseTick,
  collectAssignmentTick,
} from "./collector.mjs";

const origin = "https://canvas.example.edu";
const observed = "2026-10-31T00:00:00Z";
for (const stage of ["recover", "resume", "inspect"]) {
  test(`recovery failure reports ${stage} stage without leaking raw error text`, async () => {
    const fail = async () => {
      throw Error("PRIVATE token and content");
    };
    const result = await collectCourseTick({
      inspect:
        stage === "inspect"
          ? fail
          : async () => ({
              state: "pending",
              pending: stage === "resume" ? "resume" : "document_begin",
            }),
      operations: { retryDiscovery: fail, resumeDiscovery: fail },
      conflicts: [],
      origin,
    });
    assert.deepEqual(result, {
      state: "blocked",
      reason: `course_${stage}_failed`,
    });
    assert.ok(!JSON.stringify(result).includes("PRIVATE"));
  });
}
test("legacy assignment inspection failures carry a bounded stage code", async () => {
  const result = await collectAssignmentTick({
    inspect: async () => {
      throw Error("PRIVATE");
    },
    conflicts: [],
  });
  assert.deepEqual(result, {
    state: "blocked",
    reason: "assignment_inspect_failed",
  });
});
const row = (extra = {}) => ({
  id: 101,
  name: "Synthetic course",
  course_code: "SYN-101",
  time_zone: "America/Denver",
  enrollments: [{ enrollment_state: "active" }],
  ...extra,
});
const map = (data, next_cursor = null) =>
  mapCoursePage({ data, next_cursor }, origin, observed);

test("metadata maps only exact C2 fields and no course body", () => {
  const input = row({
    syllabus_body: "PRIVATE_BODY",
    grades: "PRIVATE_GRADE",
    updated_at: "unverified",
  });
  const result = map([input]);
  assert.deepEqual(result, {
    observed_at: observed,
    next_cursor: null,
    coverage: { state: "complete", reason: null },
    items: [
      {
        provider_id: "101",
        provider_updated_at: null,
        title: "Synthetic course",
        reference: origin + "/courses/101",
        content: "",
        fields: {
          course_code: "SYN-101",
          timezone: "America/Denver",
          enrollment_state: "active",
        },
        coverage: "complete",
        missing: [],
      },
    ],
  });
  assert.ok(!JSON.stringify(result).includes("PRIVATE"));
});

test("normalizes supported text without clipping and preserves opaque continuation", () => {
  const value = map([row({ name: "Cafe\u0301\r\nA\rB" })], "OPAQUE");
  assert.equal(value.items[0].title, "Café\nA\nB");
  assert.deepEqual(value.coverage, { state: "partial", reason: "more_pages" });
  assert.equal(value.next_cursor, "OPAQUE");
});

for (const [field, raw] of [
  ["name", null],
  ["name", ""],
  ["name", "x".repeat(501)],
  ["name", "\u0344".repeat(251)],
  ["name", "bad\u0000"],
  ["name", "\ud800"],
  ["course_code", 12],
  ["time_zone", undefined],
]) {
  test(`missing/nonportable/oversize field ${field} becomes a gap`, () => {
    const result = map([row({ [field]: raw })]);
    assert.equal(result.items[0].coverage, "partial");
    assert.ok(result.items[0].missing.length > 0);
    assert.deepEqual(result.coverage, {
      state: "partial",
      reason: "extraction_failed",
    });
  });
}

test("normalization boundary is measured after NFC in Unicode scalars", () => {
  const result = map([row({ name: "\u0344".repeat(250) })]);
  assert.equal([...result.items[0].title].length, 500);
  assert.equal(result.items[0].coverage, "complete");
});

for (const enrollments of [
  null,
  [],
  [{ enrollment_state: "active" }, { enrollment_state: "completed" }],
  [{ enrollment_state: "invented" }],
  [null],
]) {
  test("unknown or conflicting enrollment does not infer active from request filter", () => {
    const result = map([row({ enrollments })]);
    assert.equal(result.items[0].fields.enrollment_state, null);
    assert.ok(result.items[0].missing.includes("enrollment_state"));
  });
}

test("identical enrollment states are unambiguous", () => {
  assert.equal(
    map([
      row({
        enrollments: [
          { enrollment_state: "active" },
          { enrollment_state: "active" },
        ],
      }),
    ]).items[0].coverage,
    "complete",
  );
});

for (const id of [
  0,
  -1,
  1.1,
  Number.MAX_SAFE_INTEGER + 1,
  true,
  null,
  "01",
  "x",
  "1".repeat(21),
]) {
  test("invalid provider ID invalidates the whole page", () =>
    assert.throws(() => map([row({ id })]), /invalid_course_page/));
}
test("duplicate provider IDs and oversized collections are rejected atomically", () => {
  assert.throws(() => map([row(), row({ id: "101" })]), /invalid_course_page/);
  assert.throws(
    () => map(Array.from({ length: 51 }, (_, id) => row({ id: id + 1 }))),
    /invalid_course_page/,
  );
});
test("empty successful page remains a real terminal observation", () => {
  assert.equal(map([]).coverage.state, "complete");
});
