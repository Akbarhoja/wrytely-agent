import assert from "node:assert/strict";
import test from "node:test";
import { makeReader } from "./probe.mjs";
const origin = "https://canvas.example.edu";
const start = `${origin}/api/v1/courses/101/assignments?per_page=50&override_assignment_dates=true`;
const next = start + "&page=opaque%2Cbookmark";
function response(body = [{ id: 17, course_id: 101 }], options = {}) {
  const result = new Response(options.raw ?? JSON.stringify(body), {
    status: options.status ?? 200,
    headers: { "content-type": "application/json", ...options.headers },
  });
  Object.defineProperty(result, "url", { value: options.url ?? start });
  return result;
}
test("assignment reader fetches exactly one page with requesting-user dates", async () => {
  const calls = [];
  const reader = makeReader(origin, async (url, options) => {
    calls.push(url);
    assert.equal(options.credentials, "include");
    assert.equal(options.redirect, "error");
    assert.equal(options.cache, "no-store");
    return response(undefined, { headers: { link: `<${next}>; rel="next"` } });
  });
  assert.deepEqual(await reader.assignmentPage("101"), {
    data: [{ id: 17, course_id: 101 }],
    next_cursor: next,
  });
  assert.deepEqual(calls, [start]);
});
test("assignment continuation fetches only the supplied bounded next page", async () => {
  const calls = [];
  const reader = makeReader(origin, async (url) => {
    calls.push(url);
    return response([], { url });
  });
  assert.deepEqual(await reader.assignmentPage("101", next), {
    data: [],
    next_cursor: null,
  });
  assert.deepEqual(calls, [next]);
});
for (const cursor of [
  next.replace("/101/", "/102/"),
  next.replace(origin, "https://evil.example"),
  next.replace("true", "false"),
  next + "&access_token=secret",
  next + "&page=2",
  next + "#x",
  next.replace("per_page=50", "per_page=100"),
  "/api/v1/courses/101/assignments",
  next + "&include[]=all_dates",
  next.replace("page=opaque%2Cbookmark", "page="),
  next + "x".repeat(4000),
]) {
  test(
    "assignment reader rejects unsafe cursor before network: " +
      String(cursor).slice(-24),
    async () => {
      let calls = 0;
      const reader = makeReader(origin, () => {
        calls++;
        return response();
      });
      await assert.rejects(
        reader.assignmentPage("101", cursor),
        /unsafe_pagination/,
      );
      assert.equal(calls, 0);
    },
  );
}
for (const [name, data] of [
  ["foreign", [{ id: 17, course_id: 102 }]],
  [
    "duplicate",
    [
      { id: 17, course_id: 101 },
      { id: 17, course_id: 101 },
    ],
  ],
  ["unsafe", [{ id: 9007199254740992, course_id: 101 }]],
  [
    "oversize",
    Array.from({ length: 51 }, (_, i) => ({ id: i + 1, course_id: 101 })),
  ],
  ["noncollection", {}],
]) {
  test(
    "assignment reader rejects " + name + " provider collection",
    async () => {
      const reader = makeReader(origin, async () => response(data));
      await assert.rejects(reader.assignmentPage("101"), /invalid_collection/);
    },
  );
}
test("assignment reader rejects foreign continuation and cycles without following", async () => {
  for (const target of [start, next.replace("/101/", "/102/")]) {
    let calls = 0;
    const reader = makeReader(origin, async () => {
      calls++;
      return response(undefined, {
        headers: { link: `<${target}>; rel="next"` },
      });
    });
    await assert.rejects(
      reader.assignmentPage("101"),
      /pagination_cycle|unsafe_pagination/,
    );
    assert.equal(calls, 1);
  }
});
test("assignment reader rejects login, redirects and bounded JSON failures", async () => {
  for (const options of [
    { status: 401 },
    { url: origin + "/login" },
    { raw: "<html>" },
    { raw: '"' + "x".repeat(1024 * 1024) + '"' },
  ]) {
    const reader = makeReader(origin, async () => response(undefined, options));
    await assert.rejects(reader.assignmentPage("101"));
  }
});
