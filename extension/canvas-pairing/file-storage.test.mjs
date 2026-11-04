import test from "node:test";
import assert from "node:assert/strict";
import { readStorageFile, CDN_ORIGIN, FILE_ORIGIN } from "./file-storage.mjs";
const url = `${CDN_ORIGIN}/b88c0ad8-5e62-4e73-9b10-0d6f3d5e0b9e/sample.txt?token=opaque&content_type=text%2Fplain`;
const run = (transport, extra = {}) =>
  readStorageFile({
    url,
    contentType: "text/plain",
    identity: async () => {},
    transport,
    ...extra,
  });
for (const bad of [
  url.replace(CDN_ORIGIN, "https://evil.example"),
  url.replace("/sample.txt", "/x%2fy"),
  url.replace(
    "b88c0ad8-5e62-4e73-9b10-0d6f3d5e0b9e",
    "------------------------------------",
  ),
  url + "&token=second",
  url.replace("text%2Fplain", "application%2Fpdf"),
]) {
  test(
    "reject unsafe storage URL before transport: " + bad.split("?")[0],
    async () => {
      await assert.rejects(
        run({ fetch: () => assert.fail("must not fetch") }, { url: bad }),
        { code: "unsafe_file_url" },
      );
    },
  );
}
test("one approved redirect, omitted credentials, identity checked again before return", async () => {
  let calls = 0,
    identities = 0;
  const bytes = await run(
    {
      location: () => url,
      fetch: async (target, options) => {
        assert.equal(options.credentials, "omit");
        assert.equal(options.redirect, "manual");
        calls++;
        if (calls === 1) {
          assert.equal(target, FILE_ORIGIN + "/files/92");
          return new Response(null, { status: 302 });
        }
        assert.equal(target, url);
        return new Response("original text", {
          headers: { "content-type": "text/plain" },
        });
      },
    },
    {
      url: FILE_ORIGIN + "/files/92",
      identity: async () => {
        identities++;
      },
    },
  );
  assert.equal(new TextDecoder().decode(bytes), "original text");
  assert.equal(calls, 2);
  assert.equal(identities, 3);
});
test("unapproved redirect is never fetched", async () => {
  let calls = 0;
  await assert.rejects(
    run(
      {
        location: () => "https://evil.example/file",
        fetch: async () => {
          calls++;
          return new Response(null, { status: 302 });
        },
      },
      { url: FILE_ORIGIN + "/files/92" },
    ),
    { code: "unsafe_file_url" },
  );
  assert.equal(calls, 1);
});
test("repeat redirect stops", async () => {
  let calls = 0;
  await assert.rejects(
    run(
      {
        location: () => url,
        fetch: async () => {
          calls++;
          return new Response(null, { status: 302 });
        },
      },
      { url: FILE_ORIGIN + "/files/92" },
    ),
    { code: "unsafe_file_redirect" },
  );
  assert.equal(calls, 2);
});
for (const [name, response, code] of [
  ["forbidden", () => new Response(null, { status: 403 }), "permission_denied"],
  [
    "wrong mime",
    () => new Response("x", { headers: { "content-type": "text/html" } }),
    "file_type_mismatch",
  ],
  [
    "declared oversized",
    () =>
      new Response("x", {
        headers: {
          "content-type": "text/plain",
          "content-length": String(5 * 1024 * 1024 + 1),
        },
      }),
    "file_size_limit",
  ],
  [
    "stream oversized",
    () =>
      new Response(new Uint8Array(5 * 1024 * 1024 + 1), {
        headers: { "content-type": "text/plain" },
      }),
    "file_size_limit",
  ],
])
  test(name, async () => {
    await assert.rejects(run({ fetch: async () => response() }), { code });
  });
test("account change at end discards fetched text", async () => {
  let checks = 0;
  await assert.rejects(
    run(
      {
        fetch: async () =>
          new Response("private", {
            headers: { "content-type": "text/plain" },
          }),
      },
      {
        identity: async () => {
          if (++checks === 2) throw Error("account changed");
        },
      },
    ),
    /account changed/,
  );
});
test("a PDF MIME label alone is not a PDF", async () => {
  await assert.rejects(
    run(
      {
        fetch: async () =>
          new Response("html", {
            headers: { "content-type": "application/pdf" },
          }),
      },
      {
        url: url.replace("text%2Fplain", "application%2Fpdf"),
        contentType: "application/pdf",
      },
    ),
    { code: "invalid_pdf_signature" },
  );
});

test("unsupported restricted file stays an unsupported gap without download or conversion", async () => {
  const { prepareFileDocuments } = await import("./file-documents.mjs");
  const result = await prepareFileDocuments({
    resource_key: "101/files",
    origin: "https://canvas.example.edu",
    page: {
      data: [
        {
          id: "92",
          filename: "sample.docx",
          _wrytely_file: {
            contentType:
              "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            encoded: null,
            gap: "file_restricted",
          },
        },
      ],
      next_cursor: null,
    },
    extractFile: () => assert.fail("must not parse"),
  });
  assert.equal(result.documents[0].metadata.coverage, "unsupported");
  assert.deepEqual(result.documents[0].metadata.missing, [
    "file_restricted",
    "unsupported_format",
  ]);
  assert.equal(result.documents[0].source.text, "");
});

test("new HTML converter identity survives file preparation as html_text", async () => {
  const { prepareFileDocuments } = await import("./file-documents.mjs");
  const result = await prepareFileDocuments({
    resource_key: "101/files",
    origin: "https://canvas.example.edu",
    page: {
      data: [
        {
          id: "9",
          filename: "instructions.html",
          updated_at: null,
          _wrytely_file: {
            contentType: "text/html",
            encoded: "dGV4dA==",
            gap: null,
          },
        },
      ],
      next_cursor: null,
    },
    extractFile: async () => ({
      schema_version: 2,
      extractor_version: "canvas.html.v2",
      source: { text: "Original instructions" },
      coverage: "complete",
      missing: [],
    }),
  });
  assert.equal(result.documents[0].metadata.format, "html_text");
  assert.equal(
    result.documents[0].metadata.extractor_version,
    "canvas.html.v2",
  );
});
