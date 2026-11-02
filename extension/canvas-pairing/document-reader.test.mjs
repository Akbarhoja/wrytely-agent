import assert from "node:assert/strict";
import test from "node:test";
import { makeDocumentReader } from "./document-reader.mjs";
const origin = "https://canvas.example.edu";
function response(url, body, headers = {}) {
  const r = Response.json(body, { headers });
  Object.defineProperty(r, "url", { value: url });
  return r;
}
function fixture({
  link = "",
  profile = "7",
  wrongDetail = false,
  login = false,
  redirected = false,
} = {}) {
  const calls = [];
  const read = makeDocumentReader(origin, async (url, init) => {
    calls.push(url);
    assert.equal(init.method, "GET");
    assert.equal(init.credentials, "include");
    assert.equal(init.redirect, "error");
    assert.equal(init.cache, "no-store");
    if (url.endsWith("/users/self/profile"))
      return response(url, { id: profile });
    if (login) {
      const r = response(url, {}, {});
      return new Response(r.body, { status: 401 });
    }
    if (url.includes("assignments/17"))
      return response(url, {
        id: wrongDetail ? 18 : 17,
        course_id: 101,
        rubric: [{ id: "r" }],
        description: "full",
      });
    return response(
      redirected ? origin + "/other" : url,
      [{ id: 17, course_id: 101 }],
      link ? { link } : {},
    );
  });
  return { read, calls };
}
test("gets four-item assignment page and each full detail with effective dates", async () => {
  const f = fixture();
  const page = await f.read("101", "assignments", null, "7");
  assert.equal(page.data[0].description, "full");
  assert.deepEqual(page.data[0].rubric, [{ id: "r" }]);
  assert.ok(
    f.calls.includes(
      origin +
        "/api/v1/courses/101/assignments?per_page=4&override_assignment_dates=true",
    ),
  );
  assert.ok(
    f.calls.includes(
      origin +
        "/api/v1/courses/101/assignments/17?override_assignment_dates=true",
    ),
  );
  assert.equal(f.calls.filter((x) => x.endsWith("/profile")).length, 4);
});
for (const cursor of [
  "https://evil.example/api/v1/courses/101/assignments?per_page=4&override_assignment_dates=true",
  origin +
    "/api/v1/courses/102/assignments?per_page=4&override_assignment_dates=true",
  origin +
    "/api/v1/courses/101/assignments?per_page=4&override_assignment_dates=true&access_token=private",
  origin +
    "/api/v1/courses/101/assignments?per_page=4&override_assignment_dates=false",
  origin +
    "/api/v1/courses/101/assignments?per_page=4&override_assignment_dates=true&page=1&page=2",
  origin +
    "/api/v1/courses/101/assignments?per_page=4&override_assignment_dates=true#fragment",
]) {
  test(
    "rejects unapproved cursor before any provider request: " +
      cursor.split("?")[0],
    async () => {
      const f = fixture();
      await assert.rejects(
        f.read("101", "assignments", cursor, "7"),
        /unsafe_pagination/,
      );
      assert.equal(f.calls.length, 0);
    },
  );
}
test("malformed next header cannot silently certify last page", async () => {
  await assert.rejects(
    fixture({ link: "malformed-private-link" }).read(
      "101",
      "assignments",
      null,
      "7",
    ),
    /invalid_pagination/,
  );
});
test("does not follow a cross-course next link", async () => {
  const f = fixture({
    link: `<${origin}/api/v1/courses/102/assignments?per_page=4&override_assignment_dates=true&page=2>; rel="next"`,
  });
  await assert.rejects(
    f.read("101", "assignments", null, "7"),
    /unsafe_pagination/,
  );
  assert.ok(f.calls.every((url) => !url.includes("/102/")));
});
test("account switch blocks before a course read", async () => {
  const f = fixture({ profile: "8" });
  await assert.rejects(
    f.read("101", "assignments", null, "7"),
    /canvas_account_changed/,
  );
  assert.equal(f.calls.length, 1);
});
test("expired login returns a controlled stop", async () => {
  await assert.rejects(
    fixture({ login: true }).read("101", "assignments", null, "7"),
    /login_required/,
  );
});
test("detail must match the requested assignment", async () => {
  await assert.rejects(
    fixture({ wrongDetail: true }).read("101", "assignments", null, "7"),
    /invalid_collection/,
  );
});
test("response URL changes are rejected", async () => {
  await assert.rejects(
    fixture({ redirected: true }).read("101", "assignments", null, "7"),
    /invalid_response/,
  );
});

test("same-resource opaque pagination tokens are preserved", async () => {
  const next =
    origin +
    "/api/v1/courses/101/assignments?per_page=4&override_assignment_dates=true&page=opaque-A";
  const f = fixture({ link: `<${next}>; rel="next"` });
  assert.equal(
    (await f.read("101", "assignments", null, "7")).next_cursor,
    next,
  );
});

test("an account change during the response blocks return of its content", async () => {
  let subject = "7";
  const read = makeDocumentReader(origin, async (url) => {
    if (url.endsWith("/profile")) return response(url, { id: subject });
    subject = "8";
    return response(url, [
      { id: 17, course_id: 101, description: "PRIVATE_OTHER_ACCOUNT" },
    ]);
  });
  await assert.rejects(
    read("101", "assignments", null, "7"),
    /canvas_account_changed/,
  );
});

for (const kind of ["announcements", "discussions"]) {
  test(`reads full ${kind} prompt through exact selected-course discussion API`, async () => {
    const calls = [],
      announcement = kind === "announcements";
    const reader = makeDocumentReader(origin, async (url) => {
      calls.push(url);
      if (url.endsWith("/profile")) return response(url, { id: 7 });
      assert.ok(
        url.startsWith(origin + "/api/v1/courses/101/discussion_topics"),
      );
      assert.ok(!url.includes("/entries") && !url.includes("/view"));
      return response(
        url,
        url.includes("/50")
          ? {
              id: 50,
              is_announcement: announcement,
              message: "<p>Full prompt</p>",
              require_initial_post: true,
              user_can_see_posts: false,
            }
          : [{ id: 50, is_announcement: announcement }],
      );
    });
    const page = await reader("101", kind, null, "7");
    assert.equal(page.data[0].message, "<p>Full prompt</p>");
    assert.ok(
      calls.includes(
        origin +
          `/api/v1/courses/101/discussion_topics?per_page=4&only_announcements=${announcement}`,
      ),
    );
  });
}

test("an announcement cannot be mislabeled as a discussion prompt", async () => {
  const reader = makeDocumentReader(origin, async (url) =>
    response(
      url,
      url.endsWith("/profile")
        ? { id: 7 }
        : url.includes("/50")
          ? { id: 50, is_announcement: true }
          : [{ id: 50 }],
    ),
  );
  await assert.rejects(
    reader("101", "discussions", null, "7"),
    /invalid_collection/,
  );
});
