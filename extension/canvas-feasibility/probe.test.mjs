import assert from "node:assert/strict";
import test from "node:test";
import { checkedOrigin, makeReader, probeCanvas } from "./probe.mjs";

const origin = "https://canvas.example.edu";
const json = (value, headers = {}) =>
  new Response(JSON.stringify(value), {
    headers: { "content-type": "application/json", ...headers },
  });

test("a malformed trailing next link cannot silently close pagination", async () => {
  const reader = makeReader(origin, () =>
    json([], {
      Link: `<${origin}/api/v1/courses?page=1>; rel="current", malformed-next`,
    }),
  );
  await assert.rejects(reader.list("/api/v1/courses"), /invalid_pagination/);
});

test("exact HTTPS origin rejects credentials, ports, paths and wildcards", () => {
  assert.equal(checkedOrigin(origin), origin);
  for (const value of [
    "http://canvas.example.edu",
    origin + "/x",
    "https://u:p@canvas.example.edu",
    "https://*.example.edu",
    origin + ":8443",
    origin + "?x=1",
  ]) {
    assert.throws(() => checkedOrigin(value), /invalid_origin/);
  }
});

test("pagination follows opaque next links using GET only and included session", async () => {
  const calls = [];
  const reader = makeReader(origin, async (url, options) => {
    calls.push(url);
    assert.equal(options.method, "GET");
    assert.equal(options.credentials, "include");
    assert.equal(options.redirect, "error");
    return calls.length === 1
      ? json([{ id: 1 }], {
          Link: `<${origin}/api/v1/courses?opaque=next>; rel="next"`,
        })
      : json([{ id: 2 }]);
  });
  assert.deepEqual(await reader.list("/api/v1/courses"), [
    { id: 1 },
    { id: 2 },
  ]);
  assert.equal(calls[1], origin + "/api/v1/courses?opaque=next");
});

for (const next of [
  "https://evil.example/api/v1/courses",
  origin + "/api/v1/users",
  origin + "/api/v1/courses?access_token=secret",
]) {
  test(
    "reject unsafe next link before fetching it: " + new URL(next).pathname,
    async () => {
      let count = 0;
      const reader = makeReader(origin, async () => {
        count++;
        return json([], { Link: `<${next}>; rel="next"` });
      });
      await assert.rejects(reader.list("/api/v1/courses"), /unsafe_pagination/);
      assert.equal(count, 1);
    },
  );
}

test("cycles and pagination limits fail rather than claiming complete", async () => {
  const response = () =>
    json([], { Link: `<${origin}/api/v1/courses?per_page=50>; rel="next"` });
  await assert.rejects(
    makeReader(origin, response).list("/api/v1/courses"),
    /pagination_cycle/,
  );
  const reader = makeReader(
    origin,
    () =>
      json([], {
        Link: `<${origin}/api/v1/courses?page=2>; rel="next"`,
      }),
    1,
  );
  await assert.rejects(reader.list("/api/v1/courses"), /page_limit/);
});

test("HTML login, oversized streams and non-array pages cannot look successful", async () => {
  await assert.rejects(
    makeReader(origin, () => new Response("login")).get("/api/v1/courses"),
    /login_or_non_json/,
  );
  await assert.rejects(
    makeReader(origin, () => json("x".repeat(1024 * 1024))).get(
      "/api/v1/courses",
    ),
    /size_limit/,
  );
  await assert.rejects(
    makeReader(origin, () => json({})).list("/api/v1/courses"),
    /invalid_collection/,
  );
});

function provider({ switchAt = Infinity, forbidden = false } = {}) {
  let identities = 0;
  return async (url) => {
    const path = new URL(url).pathname;
    if (path.endsWith("/profile"))
      return json({
        id: ++identities >= switchAt ? 20 : 10,
        name: "PRIVATE_NAME",
      });
    if (path === "/api/v1/courses")
      return json([{ id: 101, name: "PRIVATE_COURSE" }, { id: 102 }]);
    if (path.endsWith("/assignments"))
      return forbidden
        ? new Response("PRIVATE_ERROR", { status: 403 })
        : json([
            {
              id: 4,
              description: "PRIVATE_BODY",
              rubric: [{ description: "PRIVATE_RUBRIC" }],
            },
          ]);
    if (path.endsWith("/discussion_topics"))
      return json([{ id: 5, user_can_see_posts: true }]);
    if (path.endsWith("/view"))
      return json({ view: [{ message: "PRIVATE_DISCUSSION" }] });
    return json({ syllabus_body: "PRIVATE_SYLLABUS" });
  };
}

test("two-course fixture reads syllabus, assignment/rubric and discussion without leaking content", async () => {
  const report = await probeCanvas(
    { origin, courseIds: [101, 102] },
    provider(),
  );
  assert.equal(report.discoveredCourses, 2);
  assert.equal(report.courses.length, 2);
  assert.equal(report.courses[0].resources.assignments.withRubric, 1);
  assert.equal(report.courses[0].resources.discussion.viewRead, true);
  assert.equal(report.courses[0].resources.syllabus.linkedDocumentsRead, false);
  assert.ok(!JSON.stringify(report).includes("PRIVATE"));
});

test("account switch after resource read discards entire report", async () => {
  await assert.rejects(
    probeCanvas({ origin, courseIds: [101] }, provider({ switchAt: 4 })),
    /account_switched_discarded/,
  );
});

test("restricted resources are explicit and raw provider failure is omitted", async () => {
  const report = await probeCanvas(
    { origin, courseIds: [101] },
    provider({ forbidden: true }),
  );
  assert.deepEqual(report.courses[0].resources.assignments, {
    state: "incomplete",
    reason: "permission_denied",
  });
  assert.ok(!JSON.stringify(report).includes("PRIVATE_ERROR"));
});

test("absent consenting course stops before any course content read", async () => {
  const calls = [];
  const fixture = provider();
  await assert.rejects(
    probeCanvas({ origin, courseIds: [999] }, (url) => {
      calls.push(url);
      return fixture(url);
    }),
    /course_not_accessible/,
  );
  assert.ok(calls.every((url) => !new URL(url).pathname.includes("/courses/")));
});
