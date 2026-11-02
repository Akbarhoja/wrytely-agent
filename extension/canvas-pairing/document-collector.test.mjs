import assert from "node:assert/strict";
import test from "node:test";
import {
  collectDocumentTick,
  prepareCollectedDocuments,
} from "./document-collector.mjs";
const origin = "https://canvas.example.edu";
const inspection = () => ({
  state: "active",
  pending: null,
  needs_resume: false,
  courses_closed: true,
  document_active: false,
  document_journal: true,
  academic: null,
  checkpoint: { sequence: 1, next_cursor: null },
  open_keys: ["101/pages"],
  selected_courses: ["101"],
  seen_count: 2,
  coverage: null,
});

test("worker restart continues a persisted document before reading another source", async () => {
  const calls = [];
  const current = { ...inspection(), document_active: true };
  const result = await collectDocumentTick({
    inspect: async () => current,
    operations: { continueDocumentPage: async () => calls.push("continue") },
    readPage: async () => assert.fail("must not recapture pending original"),
    conflicts: [],
    origin,
  });
  assert.deepEqual(calls, ["continue"]);
  assert.equal(result.state, "progress");
  assert.equal(result.action, "document_step");
  assert.equal("checkpoint" in result, false);
});
test("receipt replay is processed before either document continuation or source reads", async () => {
  const current = {
    ...inspection(),
    document_active: true,
    pending: "document_batch",
  };
  const calls = [];
  await collectDocumentTick({
    inspect: async () => current,
    conflicts: [],
    origin,
    operations: { collectCoursePage: async () => calls.push("recover") },
    readPage: async () => assert.fail("must not read before replay"),
  });
  assert.deepEqual(calls, ["recover"]);
});
test("a partial original cannot close its resource as complete", async () => {
  const current = {
    ...inspection(),
    academic: {
      resource_key: "101/pages",
      incomplete: true,
      last_page_coverage: "complete",
    },
  };
  let outcome;
  await collectDocumentTick({
    inspect: async () => current,
    conflicts: [],
    origin,
    operations: {
      finishDocumentResource: async (input) => {
        outcome = input;
      },
    },
  });
  assert.deepEqual(outcome, {
    resource_key: "101/pages",
    outcome: "partial",
    reason: "extraction_failed",
  });
});
test("locked body is withheld from extraction and a forged nonempty result rejects", async () => {
  const page = {
    data: [
      {
        page_id: 20,
        title: "Private page",
        body: "PRIVATE_LOCKED",
        locked_for_user: true,
      },
    ],
    next_cursor: null,
  };
  const extract = async (course_id, kind, items) => {
    assert.equal(items[0].html, null);
    return {
      schema_version: 2,
      resource: { course_id, kind },
      extractor_version: "canvas.html.v1",
      items: [
        {
          provider_id: "20",
          text: "forged",
          coverage: "partial",
          missing: ["html_text_only"],
        },
      ],
    };
  };
  await assert.rejects(
    prepareCollectedDocuments({
      page,
      resource_key: "101/pages",
      extract,
      origin,
    }),
  );
});
test("a response for a different course cannot become this course's evidence", async () => {
  await assert.rejects(
    prepareCollectedDocuments({
      resource_key: "101/pages",
      origin,
      page: {
        data: [{ page_id: 20, title: "Page", body: "<p>Hello</p>" }],
        next_cursor: null,
      },
      extract: async () => ({
        schema_version: 2,
        resource: { course_id: "102", kind: "pages" },
        extractor_version: "canvas.html.v1",
        items: [],
      }),
    }),
  );
});
