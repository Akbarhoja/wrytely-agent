import test from "node:test";
import assert from "node:assert/strict";
import {
  linkedFileIds,
  readLinkedFilePage,
  LINKED_FILES_CURSOR,
} from "./linked-files.mjs";
import { makeDocumentReader } from "./document-reader.mjs";
import { prepareFileDocuments } from "./file-documents.mjs";
const origin = "https://canvas.example.edu";
const link = (id) =>
  `<a href="${origin}/courses/101/files/${id}?wrap=1">manual</a>`;
const denied = () => Object.assign(Error(), { code: "permission_denied" });

test("only same-course actual anchor hrefs are discoverable; no script/title/foreign/credential links", () => {
  assert.deepEqual(
    linkedFileIds(
      [
        link(17),
        link(17),
        '<a href="/api/v1/courses/101/files/18">starter</a>',
        `<script>${link(19)}</script>`,
        `<!-- ${link(20)} -->`,
        `<a title='example href="/courses/101/files/21"'>not a link</a>`,
        '<a href="https://evil.example/courses/101/files/22">outside</a>',
        '<a href="/courses/102/files/23">other course</a>',
        '<a href="/courses/101/files/24?token=private">credential</a>',
        '<a href="/courses/101/files/25" href="/courses/101/files/26">duplicate</a>',
        '<a href=/courses/101/files/27 href="/courses/101/files/28">duplicate</a>',
        '<a href="/courses/101/files/29/../30">traversal</a>',
      ].join(""),
      origin,
      "101",
    ),
    ["17", "18"],
  );
});

function fixture({
  selectedKinds = ["files", "assignments", "syllabus"],
  fileDenied = false,
} = {}) {
  const calls = [];
  const get = async (path, query = "") => {
    calls.push(path + query);
    if (path === "/api/v1/courses/101")
      return { data: { id: 101, syllabus_body: link(17) } };
    if (path === "/api/v1/courses/101/assignments")
      return {
        data: [
          { id: 31, course_id: 101, description: link(17) + link(18) },
          {
            id: 32,
            course_id: 101,
            locked_for_user: true,
            description: link(19),
          },
          { id: 33, course_id: 101, quiz_id: 9, description: link(20) },
        ],
        link: "",
      };
    const id = path.split("/").at(-1);
    if (path.includes("/files/") && !path.endsWith("/public_url")) {
      if (fileDenied && id === "17") throw denied();
      return {
        data: {
          id: Number(id),
          filename: `manual${id}.txt`,
          "content-type": "text/plain",
          size: 5,
          locked_for_user: false,
          url: `https://cdn.inst-fs-iad-prod.inscloudgate.net/b88c0ad8-5e62-4e73-9b10-0d6f3d5e0b9e/manual.txt?token=opaque&content_type=text%2Fplain`,
        },
      };
    }
    assert.fail(path);
  };
  const transport = {
    fetch: async () =>
      new Response("hello", { headers: { "content-type": "text/plain" } }),
  };
  const read = (cursor) =>
    readLinkedFilePage({
      course: "101",
      cursor,
      origin,
      get,
      transport,
      identity: async () => {},
      selectedKinds,
    });
  return { calls, read };
}

test("restartable cursor collects direct files once with merged provenance and keeps enumeration gap", async () => {
  const f = fixture();
  let a = await f.read(null);
  assert.deepEqual(a.data, []);
  assert.ok(!a.next_cursor.includes("token"));
  a = await f.read(a.next_cursor);
  assert.deepEqual(a.data, []);
  // A new reader instance can resume using only the cursor, with no HTML or URL cache.
  const resumed = fixture();
  a = await resumed.read(a.next_cursor);
  assert.equal(a.next_cursor, null);
  assert.deepEqual(a.coverage, {
    state: "partial",
    reason: "permission_denied",
  });
  assert.deepEqual(
    a.data.map((x) => String(x.id)),
    ["17", "18"],
  );
  assert.deepEqual(a.data[0]._wrytely_linked_from, [
    "assignment:31",
    "syllabus:101",
  ]);
  assert.ok(
    resumed.calls.every(
      (p) => !p.includes("assignments") && !p.includes("quizzes"),
    ),
  );
  const prepared = await prepareFileDocuments({
    resource_key: "101/files",
    page: a,
    origin,
    extractFile: async () => ({
      schema_version: 2,
      extractor_version: "canvas.text.v1",
      source: { text: "hello" },
      coverage: "complete",
      missing: [],
    }),
  });
  assert.equal(prepared.coverage.state, "partial");
  assert.equal(prepared.documents[0].metadata.coverage, "complete");
  assert.deepEqual(prepared.documents[0].object_fields.linked_from, [
    "assignment:31",
    "syllabus:101",
  ]);
});

test("files permission alone cannot read parent bodies", async () => {
  const f = fixture({ selectedKinds: ["files"] });
  await assert.rejects(f.read(null), { code: "permission_denied" });
  assert.deepEqual(f.calls, []);
});
test("a forbidden direct file does not prevent a second accessible file", async () => {
  const f = fixture({ fileDenied: true });
  let a = await f.read(null);
  a = await f.read(a.next_cursor);
  a = await f.read(a.next_cursor);
  assert.deepEqual(
    a.data.map((x) => String(x.id)),
    ["18"],
  );
  assert.equal(a.coverage.state, "partial");
});
test("changed parent scope and foreign cursors are rejected before provider reads", async () => {
  const f = fixture();
  const a = await f.read(null);
  const changed = fixture({ selectedKinds: ["files", "assignments"] });
  await assert.rejects(changed.read(a.next_cursor), {
    code: "unsafe_pagination",
  });
  assert.deepEqual(changed.calls, []);
  const state = JSON.parse(a.next_cursor.slice(LINKED_FILES_CURSOR.length));
  state.next = origin + "/api/v1/courses/102/assignments?per_page=4";
  state.stage = "assignments";
  f.calls.length = 0;
  await assert.rejects(f.read(LINKED_FILES_CURSOR + JSON.stringify(state)), {
    code: "unsafe_pagination",
  });
  assert.deepEqual(f.calls, []);
});
test("canonical cursor bounds reject invalid offsets and invented provenance", async () => {
  const f = fixture();
  const a = await f.read(null);
  const initial = JSON.parse(a.next_cursor.slice(LINKED_FILES_CURSOR.length));
  for (const mutate of [
    (s) => (s.offset = -1),
    (s) => (s.offset = 10),
    (s) => (s.links[0][1] = ["syllabus:102"]),
    (s) => (s.links[0][0] = "https://evil.example"),
    (s) => (s.parents = ["files"]),
    (s) => (s.extra = "private"),
  ]) {
    const s = structuredClone(initial);
    mutate(s);
    f.calls.length = 0;
    await assert.rejects(f.read(LINKED_FILES_CURSOR + JSON.stringify(s)), {
      code: "unsafe_pagination",
    });
    assert.deepEqual(f.calls, []);
  }
});
test("pagination is durable, bounded and cannot leave the selected course", async () => {
  let reads = 0;
  const get = async () => ({
    data: [{ id: ++reads, course_id: 101, description: link(17) }],
    link: `<${origin}/api/v1/courses/101/assignments?per_page=4&page=${reads + 1}>; rel="next"`,
  });
  let cursor = null;
  for (let i = 0; i < 2; i++)
    cursor = (
      await readLinkedFilePage({
        course: "101",
        cursor,
        origin,
        get,
        selectedKinds: ["files", "assignments"],
      })
    ).next_cursor;
  assert.equal(reads, 2);
  assert.ok(cursor.includes("page=3"));
});
test("integrated reader falls back only on an initial listing denial and preserves profile checks", async () => {
  const calls = [];
  const fetchImpl = async (url) => {
    calls.push(url);
    if (url.endsWith("/users/self/profile")) {
      const r = Response.json({ id: 7 });
      Object.defineProperty(r, "url", { value: url });
      return r;
    }
    if (url.includes("/files?")) return new Response(null, { status: 403 });
    if (url.includes("/assignments?")) {
      const r = Response.json([]);
      Object.defineProperty(r, "url", { value: url });
      return r;
    }
    assert.fail(url);
  };
  const read = makeDocumentReader(origin, fetchImpl);
  const p = await read("101", "files", null, "7", ["files", "assignments"]);
  assert.deepEqual(p.data, []);
  assert.equal(p.coverage.reason, "permission_denied");
  assert.equal(p.next_cursor, null);
  assert.ok(calls.some((x) => x.includes("/assignments?")));
  calls.length = 0;
  await assert.rejects(read("101", "files", null, "7", ["files"]), {
    code: "permission_denied",
  });
  assert.ok(!calls.some((x) => x.includes("/assignments?")));
});

test("a denied file detail never masquerades as a denied listing", async () => {
  let parentReads = 0;
  const fetchImpl = async (url) => {
    let r;
    if (url.endsWith("/users/self/profile")) r = Response.json({ id: 7 });
    else if (url.endsWith("/files?per_page=4")) r = Response.json([{ id: 17 }]);
    else if (url.endsWith("/files/17"))
      return new Response(null, { status: 403 });
    else {
      parentReads++;
      assert.fail(url);
    }
    Object.defineProperty(r, "url", { value: url });
    return r;
  };
  await assert.rejects(
    makeDocumentReader(origin, fetchImpl)("101", "files", null, "7", [
      "files",
      "assignments",
    ]),
    { code: "permission_denied" },
  );
  assert.equal(parentReads, 0);
});

test("oversized dependency discovery stops explicitly without silently clipping", () => {
  assert.throws(
    () =>
      linkedFileIds(
        Array.from({ length: 65 }, (_, i) => link(i + 1)).join(""),
        origin,
        "101",
      ),
    { code: "size_limit" },
  );
});

test("network and login errors do not advance the persisted continuation", async () => {
  const f = fixture();
  const first = await f.read(null);
  const s = JSON.parse(first.next_cursor.slice(LINKED_FILES_CURSOR.length));
  s.stage = "files";
  s.next = null;
  const cursor = LINKED_FILES_CURSOR + JSON.stringify(s);
  for (const code of [
    "login_required",
    "canvas_account_changed",
    "file_network_failed",
  ]) {
    await assert.rejects(
      readLinkedFilePage({
        course: "101",
        cursor,
        origin,
        selectedKinds: ["files", "assignments", "syllabus"],
        get: async () => {
          throw Object.assign(Error(), { code });
        },
      }),
      { code },
    );
    assert.equal(
      JSON.parse(cursor.slice(LINKED_FILES_CURSOR.length)).offset,
      0,
    );
  }
});
