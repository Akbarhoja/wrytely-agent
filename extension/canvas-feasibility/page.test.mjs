import assert from "node:assert/strict";
import test from "node:test";
import { makeReader } from "./probe.mjs";

const origin = "https://canvas.example.edu";
const start = `${origin}/api/v1/courses?enrollment_state=active&per_page=50`;
const next = `${start}&page=opaque%2Cbookmark`;
function response(
  body = [],
  { url = start, status = 200, headers = {}, raw } = {},
) {
  const result = new Response(raw ?? JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
  Object.defineProperty(result, "url", { value: url });
  return result;
}

test("one tick fetches one bounded active-course page with session transport", async () => {
  const calls = [];
  const api = makeReader(origin, async (url, options) => {
    calls.push(url);
    assert.equal(options.method, "GET");
    assert.equal(options.credentials, "include");
    assert.equal(options.redirect, "error");
    assert.equal(options.cache, "no-store");
    assert.ok(options.signal instanceof AbortSignal);
    return response([{ id: 1 }], {
      headers: { link: `<${next}>; rel="next"` },
    });
  });
  assert.deepEqual(await api.coursePage(), {
    data: [{ id: 1 }],
    next_cursor: next,
  });
  assert.deepEqual(calls, [start]);
});

test("opaque continuation is returned and fetched only on the next explicit tick", async () => {
  const calls = [];
  const api = makeReader(origin, async (url) => {
    calls.push(url);
    return response([{ id: 2 }], { url });
  });
  assert.deepEqual(await api.coursePage(next), {
    data: [{ id: 2 }],
    next_cursor: null,
  });
  assert.deepEqual(calls, [next]);
});

const badCursors = [
  "https://evil.example/api/v1/courses?per_page=50&enrollment_state=active",
  start.replace("https:", "http:"),
  start.replace("/courses", "/users"),
  start.replace("canvas.example.edu", "u:p@canvas.example.edu"),
  start + "#fragment",
  start + "&access_token=secret",
  start + "&include[]=syllabus_body",
  start + "&page=1&page=2",
  start.replace("per_page=50", "per_page=100"),
  start.replace("enrollment_state=active", "enrollment_state=completed"),
  start.replace("&per_page=50", ""),
  start + "&page=",
  "/api/v1/courses?enrollment_state=active&per_page=50",
  start + "&page=" + "x".repeat(4000),
  1,
];
for (const [i, cursor] of badCursors.entries()) {
  test(`unsafe persisted cursor ${i} is rejected before network`, async () => {
    let calls = 0;
    const api = makeReader(origin, () => {
      calls++;
      return response();
    });
    await assert.rejects(api.coursePage(cursor), /unsafe_pagination/);
    assert.equal(calls, 0);
  });
}

for (const [name, options, code] of [
  ["login", { status: 401 }, "login_required"],
  ["denied", { status: 403 }, "permission_denied"],
  ["rate", { status: 429 }, "rate_limited"],
  ["outage", { status: 503 }, "provider_unavailable"],
  ["partial HTTP", { status: 206 }, "invalid_response"],
  ["final URL", { url: next }, "invalid_response"],
  ["missing final URL", { url: "" }, "invalid_response"],
  ["HTML", { headers: { "content-type": "text/html" } }, "login_or_non_json"],
  ["bad UTF8", { raw: new Uint8Array([91, 34, 0xff, 34, 93]) }, "invalid_json"],
  ["bad JSON", { raw: "[" }, "invalid_json"],
  ["declared size", { headers: { "content-length": "1048577" } }, "size_limit"],
  ["stream size", { raw: " ".repeat(1048577) }, "size_limit"],
  ["Link size", { headers: { link: "x".repeat(16385) } }, "invalid_pagination"],
  [
    "trailing garbage",
    { headers: { link: `<${next}>; rel="next", bad` } },
    "invalid_pagination",
  ],
  [
    "duplicate next",
    { headers: { link: `<${next}>; rel="next", <${next}>; rel="next"` } },
    "invalid_pagination",
  ],
  [
    "self cycle",
    { headers: { link: `<${start}>; rel="next"` } },
    "pagination_cycle",
  ],
  [
    "unsafe next",
    { headers: { link: '<https://evil.example/api/v1/courses>; rel="next"' } },
    "unsafe_pagination",
  ],
]) {
  test(`controlled failure: ${name}`, async () => {
    await assert.rejects(
      makeReader(origin, () => response([], options)).coursePage(),
      (error) => error.code === code && error.message === code,
    );
  });
}

for (const data of [
  {},
  [null],
  [1],
  Array.from({ length: 51 }, () => ({ id: 1 })),
]) {
  test("invalid or oversized course collection is never a terminal empty page", async () => {
    await assert.rejects(
      makeReader(origin, () => response(data)).coursePage(),
      /invalid_collection/,
    );
  });
}

test("exact 50-row boundary and benign current/last links work", async () => {
  const data = Array.from({ length: 50 }, (_, id) => ({ id: id + 1 }));
  const api = makeReader(origin, () =>
    response(data, {
      headers: {
        link: `<${start}>; rel="current", <${next}>; rel="last"`,
      },
    }),
  );
  assert.deepEqual(await api.coursePage(), { data, next_cursor: null });
});

test("fetch and body errors never expose provider text", async () => {
  await assert.rejects(
    makeReader(origin, () => {
      throw Error("PRIVATE");
    }).coursePage(),
    (error) =>
      error.code === "network_or_redirect_blocked" &&
      !error.message.includes("PRIVATE"),
  );
  const raw = new ReadableStream({
    pull(controller) {
      controller.error(Error("PRIVATE"));
    },
  });
  await assert.rejects(
    makeReader(origin, () => response([], { raw })).coursePage(),
    (error) =>
      error.code === "invalid_json" && !error.message.includes("PRIVATE"),
  );
});

for (const [name, options, code] of [
  ["HTTP denial", { status: 401 }, "login_required"],
  ["final URL", { url: next }, "invalid_response"],
  [
    "non-JSON",
    { headers: { "content-type": "text/html" } },
    "login_or_non_json",
  ],
  [
    "declared body limit",
    { headers: { "content-length": "1048577" } },
    "size_limit",
  ],
  ["streamed body limit", {}, "size_limit"],
]) {
  test(`cleanup rejection preserves controlled ${name} failure`, async () => {
    const raw = new ReadableStream({
      start(controller) {
        controller.enqueue(new Uint8Array(1048577));
      },
      cancel() {
        throw Error("PRIVATE_PROVIDER_DETAIL");
      },
    });
    await assert.rejects(
      makeReader(origin, () => response([], { ...options, raw })).coursePage(),
      (error) => error.code === code && error.message === code,
    );
  });
}
