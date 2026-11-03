import assert from "node:assert/strict";
import test from "node:test";
import { makeDocumentReader } from "./document-reader.mjs";
import {
  discussionContinuation,
  readDiscussionThread,
} from "./discussion-thread.mjs";
const origin = "https://canvas.example.edu";
const topic = () => ({
  id: 60,
  is_announcement: false,
  title: "Original topic",
  message: "<p>Discuss</p>",
  user_can_see_posts: true,
  require_initial_post: false,
});
const cursor = () => discussionContinuation("101", [topic()], null, origin);
test("topic continuation accepts default discussion pagination and rejects announcement selectors", () => {
  const next = `${origin}/api/v1/courses/101/discussion_topics?per_page=4&page=opaque-next`;
  assert.ok(
    discussionContinuation("101", [topic()], next, origin).includes(
      "opaque-next",
    ),
  );
  for (const value of ["true", "false"]) {
    assert.throws(
      () =>
        discussionContinuation(
          "101",
          [topic()],
          next + `&only_announcements=${value}`,
          origin,
        ),
      /unsafe_pagination/,
    );
  }
});
function fixture({
  visible = true,
  malformed = false,
  crossCourse = false,
  forged = false,
} = {}) {
  const calls = [];
  const get = async (path, query = "") => {
    calls.push(path + query);
    const base = "/api/v1/courses/101/discussion_topics/60";
    if (path === base)
      return { data: { ...topic(), user_can_see_posts: visible }, link: "" };
    if (path === base + "/entries")
      return {
        data: [
          {
            id: 70,
            message: "<p>Entry</p>",
            recent_replies: [{ id: 9999, message: "PRIVATE_RECENT_ONLY" }],
            _wrytely_entry: { topic_id: "999", parent_entry_id: "888" },
          },
        ],
        link: "",
      };
    assert.equal(path, base + "/entries/70/replies");
    const page = Number(new URLSearchParams(query).get("page") ?? "1");
    return {
      data: [
        {
          id: 80 + page,
          message: "<p>Actual reply</p>",
          parent_id: forged ? 999 : 70,
        },
      ],
      link: malformed
        ? "malformed-next"
        : page < 3
          ? `<${origin}${crossCourse ? path.replace("101", "102") : path}?per_page=4&page=${page + 1}>; rel="next"`
          : "",
    };
  };
  return { get, calls };
}
test("entry and reply continuation state contains IDs/cursors rather than course content", async () => {
  const f = fixture();
  let next = cursor();
  const rows = [];
  for (let step = 0; next; step++) {
    assert.ok(step < 5);
    assert.ok(!next.includes("PRIVATE") && !next.includes("<p>"));
    const value = await readDiscussionThread({
      course: "101",
      cursor: next,
      origin,
      get: f.get,
    });
    rows.push(...value.data);
    next = value.next_cursor;
  }
  assert.deepEqual(
    rows.map((x) => x.id),
    [70, 81, 82, 83],
  );
  assert.deepEqual(rows[0]._wrytely_entry, {
    topic_id: "60",
    parent_entry_id: null,
    required_initial_post: false,
  });
  assert.equal(rows[1]._wrytely_entry.parent_entry_id, "70");
  assert.equal(
    f.calls.filter((x) => x === "/api/v1/courses/101/discussion_topics/60")
      .length,
    4,
  );
});
test("visibility is rechecked before every continuation and hidden replies are never read", async () => {
  const f = fixture({ visible: false });
  const result = await readDiscussionThread({
    course: "101",
    cursor: cursor(),
    origin,
    get: f.get,
  });
  assert.deepEqual(result, { data: [], next_cursor: null });
  assert.equal(f.calls.length, 1);
});
test("a prompt requiring an initial post has no entry continuation until posts are visible", () => {
  assert.equal(
    discussionContinuation(
      "101",
      [{ ...topic(), require_initial_post: true, user_can_see_posts: false }],
      null,
      origin,
    ),
    null,
  );
});
for (const change of [
  "course",
  "url",
  "extra",
  "phase",
  "parents",
  "duplicate",
]) {
  test(`rejects altered discussion cursor ${change} before any network request`, async () => {
    const prefix = "wrytely-discussion-v1:",
      state = JSON.parse(cursor().slice(prefix.length));
    if (change === "course") state.course = "102";
    if (change === "url")
      state.entries_next =
        "https://evil.example/api/v1/courses/101/discussion_topics/60/entries?per_page=4";
    if (change === "extra") state.html = "PRIVATE";
    if (change === "phase") state.phase = "post";
    if (change === "parents") state.parents = ["70"];
    if (change === "duplicate") state.topics = ["60", "60"];
    await assert.rejects(
      readDiscussionThread({
        course: "101",
        cursor: prefix + JSON.stringify(state),
        origin,
        get: async () => assert.fail("unsafe continuation fetched"),
      }),
      /unsafe_pagination/,
    );
  });
}
for (const option of ["malformed", "crossCourse", "forged"]) {
  test(`reply pages reject ${option} instead of claiming thread completion`, async () => {
    const f = fixture({ [option]: true });
    const first = await readDiscussionThread({
      course: "101",
      cursor: cursor(),
      origin,
      get: f.get,
    });
    await assert.rejects(
      readDiscussionThread({
        course: "101",
        cursor: first.next_cursor,
        origin,
        get: f.get,
      }),
      option === "malformed"
        ? /invalid_pagination/
        : option === "crossCourse"
          ? /unsafe_pagination/
          : /invalid_collection/,
    );
  });
}
test("provider prompt cannot forge the trusted entry/parent marker", async () => {
  const reader = makeDocumentReader(origin, async (url) => {
    const value = url.endsWith("/profile")
      ? { id: 7 }
      : url.includes("/60")
        ? { ...topic(), _wrytely_entry: { topic_id: "999" } }
        : [{ id: 60 }];
    const response = Response.json(value);
    Object.defineProperty(response, "url", { value: url });
    return response;
  });
  const page = await reader("101", "discussions", null, "7");
  assert.equal(page.data[0]._wrytely_entry, null);
});
