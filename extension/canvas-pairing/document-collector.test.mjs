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
test("lease expiry between inspection and document commit uses existing recovery without rereading", async () => {
  const calls = [];
  const result = await collectDocumentTick({
    inspect: async () => inspection(),
    readPage: async () => {
      calls.push("read");
      return { data: [], next_cursor: null };
    },
    operations: {
      commitDocumentPage: async () => {
        calls.push("commit");
        throw Object.assign(Error(), { code: "discovery_lease_expired" });
      },
      collectCoursePage: async () => {
        calls.push("recover");
        return { state: "progress", action: "resume" };
      },
    },
    origin,
    conflicts: ["lease_expired"],
  });
  assert.deepEqual(calls, ["read", "commit", "recover"]);
  assert.deepEqual(result, { state: "progress", action: "resume" });
});
test("lease expiry during document continuation recovers without starting a second upload", async () => {
  const calls = [];
  const result = await collectDocumentTick({
    inspect: async () => ({ ...inspection(), document_active: true }),
    operations: {
      continueDocumentPage: async () => {
        calls.push("continue");
        throw Object.assign(Error(), { code: "discovery_lease_expired" });
      },
      collectCoursePage: async () => {
        calls.push("recover");
        return { state: "progress", action: "recover" };
      },
    },
    readPage: async () => assert.fail("must not recapture pending document"),
    origin,
    conflicts: ["lease_expired"],
  });
  assert.deepEqual(calls, ["continue", "recover"]);
  assert.equal(result.state, "progress");
});
test("a replaced writer lease still stops instead of automatic recovery", async () => {
  const result = await collectDocumentTick({
    inspect: async () => ({ ...inspection(), document_active: true }),
    operations: {
      continueDocumentPage: async () => {
        throw Object.assign(Error(), { code: "discovery_lease_replaced" });
      },
      collectCoursePage: async () =>
        assert.fail("must not take over another writer"),
    },
    origin,
    conflicts: ["lease_replaced"],
  });
  assert.deepEqual(result, {
    state: "blocked",
    reason: "discovery_lease_replaced",
  });
});

test("worker restart continues a persisted document before reading another source", async () => {
  const calls = [];
  const current = { ...inspection(), document_active: true };
  const result = await collectDocumentTick({
    inspect: async () => current,
    operations: {
      continueDocumentPage: async () => {
        calls.push("continue");
        return current;
      },
    },
    readPage: async () => assert.fail("must not recapture pending original"),
    conflicts: [],
    origin,
  });
  assert.deepEqual(calls, ["continue"]);
  assert.equal(result.state, "progress");
  assert.equal(result.action, "document_step");
  assert.equal("checkpoint" in result, false);
});
test("document continuation reuses the final-checked projection without a second context/profile inspection", async () => {
  let inspections = 0;
  const result = await collectDocumentTick({
    inspect: async () => {
      inspections++;
      return { ...inspection(), document_active: true };
    },
    operations: {
      continueDocumentPage: async () => ({
        state: "active",
        seen_count: 9,
        coverage: "partial",
        checkpoint: "PRIVATE",
      }),
    },
    readPage: async () => assert.fail("must not reread original"),
    origin,
    conflicts: [],
  });
  assert.equal(inspections, 1);
  assert.equal(result.seen_count, 9);
  assert.equal(result.coverage, "partial");
  assert.ok(!JSON.stringify(result).includes("PRIVATE"));
});
test("final-check authorization failure stops instead of displaying an earlier successful projection", async () => {
  const result = await collectDocumentTick({
    inspect: async () => ({ ...inspection(), document_active: true }),
    operations: {
      continueDocumentPage: async () => {
        throw Object.assign(Error(), { code: "canvas_account_changed" });
      },
    },
    origin,
    conflicts: [],
  });
  assert.deepEqual(result, {
    state: "blocked",
    reason: "canvas_account_changed",
  });
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
        return current;
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

test("a forbidden resource is recorded as restricted so other courses can continue", async () => {
  let outcome;
  const current = inspection();
  const result = await collectDocumentTick({
    inspect: async () => current,
    conflicts: [],
    origin,
    readPage: async () => {
      throw Object.assign(Error(), { code: "permission_denied" });
    },
    operations: {
      finishDiscoveryResource: async (input) => {
        outcome = input;
        return current;
      },
    },
  });
  assert.deepEqual(outcome, {
    resource_key: "101/pages",
    outcome: "restricted",
    reason: "permission_denied",
  });
  assert.equal(result.action, "restricted_documents");
});

test("login loss is not mislabeled a course restriction or silently skipped", async () => {
  const result = await collectDocumentTick({
    inspect: async () => inspection(),
    conflicts: [],
    origin,
    readPage: async () => {
      throw Object.assign(Error(), { code: "login_required" });
    },
    operations: {
      finishDiscoveryResource: async () =>
        assert.fail("must stop for reauthentication"),
    },
  });
  assert.deepEqual(result, { state: "blocked", reason: "login_required" });
});

for (const kind of ["announcements", "discussions"]) {
  test(`maps ${kind} text without inventing author roles or reading hidden replies`, async () => {
    const raw = {
      id: 50,
      title: "Source prompt",
      message: "<p>Read this.</p>",
      posted_at: "2026-11-01T09:30:01.123456+01:00",
      require_initial_post: true,
      user_can_see_posts: false,
      assignment: { due_at: "2026-11-03T00:00:00Z" },
    };
    const result = await prepareCollectedDocuments({
      origin,
      resource_key: `101/${kind}`,
      page: { data: [raw], next_cursor: null },
      extract: async (course_id, kind, inputs) => {
        assert.equal(inputs[0].html, raw.message);
        return {
          schema_version: 2,
          extractor_version: "canvas.html.v1",
          resource: { course_id, kind },
          items: [
            {
              provider_id: "50",
              text: "Read this.",
              coverage: "partial",
              missing: ["html_text_only"],
            },
          ],
        };
      },
    });
    const document = result.documents[0];
    assert.equal(document.object_fields.author_role, null);
    assert.equal(document.metadata.coverage, "partial");
    assert.equal(document.source.text, "Read this.");
    if (kind === "announcements") {
      assert.equal(
        document.object_fields.posted_at,
        "2026-11-01T08:30:01.123456Z",
      );
      assert.ok(
        document.metadata.missing.includes("announcement_replies_unread"),
      );
    } else {
      assert.equal(document.object_fields.due_at, null);
      assert.ok(document.metadata.missing.includes("initial_post_required"));
      assert.ok(
        document.metadata.missing.includes("discussion_replies_unread"),
      );
    }
  });
}

for (const posted_at of [
  "2026-02-30T00:00:00Z",
  "2026-11-01",
  1234,
  "2026-11-01T00:00:00+24:00",
]) {
  test(`rejects malformed announcement date rather than silently rolling it forward: ${posted_at}`, async () => {
    await assert.rejects(
      prepareCollectedDocuments({
        origin,
        resource_key: "101/announcements",
        page: {
          data: [
            {
              id: 50,
              title: "Announcement",
              message: "<p>Prompt</p>",
              posted_at,
            },
          ],
          next_cursor: null,
        },
        extract: async (course_id, kind) => ({
          schema_version: 2,
          extractor_version: "canvas.html.v1",
          resource: { course_id, kind },
          items: [
            {
              provider_id: "50",
              text: "Prompt",
              coverage: "partial",
              missing: ["html_text_only"],
            },
          ],
        }),
      }),
    );
  });
}

test("a missing resource records an incomplete read, not a deletion or permission claim", async () => {
  let outcome;
  await collectDocumentTick({
    inspect: async () => inspection(),
    conflicts: [],
    origin,
    readPage: async () => {
      throw Object.assign(Error(), { code: "not_found" });
    },
    operations: {
      finishDiscoveryResource: async (value) => {
        outcome = value;
        return inspection();
      },
    },
  });
  assert.deepEqual(outcome, {
    resource_key: "101/pages",
    outcome: "partial",
    reason: "extraction_failed",
  });
});
