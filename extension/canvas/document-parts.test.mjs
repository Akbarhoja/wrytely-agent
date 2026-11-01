import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import test from "node:test";
import { prepareDocumentParts } from "./document-parts.mjs";
import { canonicalSourceBytes, sourceDigest } from "./source-digest.mjs";

const { vectors } = JSON.parse(
  await readFile(
    new URL("../../tests/fixtures/canvas_document_v2.json", import.meta.url),
    "utf8",
  ),
);

for (const vector of vectors) {
  test(`approved unchanged v2 vector: ${vector.name}`, async () => {
    const result = await prepareDocumentParts(
      vector.raw_pages === null
        ? { text: vector.raw_text }
        : { pages: vector.raw_pages },
    );
    const fields = vector.digest_payload.fields;
    assert.deepEqual(result.manifest, fields.slots);
    assert.deepEqual(result.parts, vector.parts);
    assert.equal(result.total_characters, fields.total_characters);
    assert.equal(result.total_pages, fields.total_pages);
    const payload = structuredClone(vector.digest_payload);
    Object.assign(payload.fields, {
      slots: result.manifest,
      total_characters: result.total_characters,
      total_pages: result.total_pages,
    });
    assert.equal(
      new TextDecoder().decode(canonicalSourceBytes(payload)),
      vector.canonical_utf8,
    );
    assert.equal(await sourceDigest(payload), vector.sha256);
    assert.equal(
      result.parts.map((p) => p.text).join(""),
      vector.normalized_text,
    );
    assert.deepEqual(Object.keys(result).sort(), [
      "manifest",
      "parts",
      "total_characters",
      "total_pages",
      "unrepresented_pages",
    ]);
  });
}

test("normalize whole text before Unicode code-point splits and exact hashes", async () => {
  const result = await prepareDocumentParts({
    text: "e\u0301\r\n📚Z",
    sectionCharacters: 2,
  });
  assert.deepEqual(result.parts, [
    { slot: 0, text: "é\n" },
    { slot: 1, text: "📚Z" },
  ]);
  assert.deepEqual(
    result.manifest.map((s) => [s.start, s.end, s.page]),
    [
      [0, 2, null],
      [2, 4, null],
    ],
  );
  for (const part of result.parts)
    assert.equal(
      result.manifest[part.slot].text_sha256,
      createHash("sha256").update(part.text).digest("hex"),
    );
});

test("PDF separator belongs to following nonempty page, retaining original gaps", async () => {
  const result = await prepareDocumentParts({
    pages: ["", "A\r\n", "", "e\u0301📚", ""],
    sectionCharacters: 2,
  });
  assert.deepEqual(
    result.parts.map((p) => p.text),
    ["A\n", "\né", "📚"],
  );
  assert.deepEqual(
    result.manifest.map((p) => p.page),
    [2, 4, 4],
  );
  assert.deepEqual(result.unrepresented_pages, [1, 3, 5]);
  assert.equal(result.total_pages, 5);
  assert.equal(result.total_characters, 5);
});

test("empty text and empty observed PDF pages never fabricate sections", async () => {
  assert.deepEqual(await prepareDocumentParts({ text: "" }), {
    manifest: [],
    parts: [],
    total_characters: 0,
    total_pages: null,
    unrepresented_pages: [],
  });
  const pdf = await prepareDocumentParts({ pages: ["", ""] });
  assert.deepEqual(pdf.manifest, []);
  assert.deepEqual(pdf.unrepresented_pages, [1, 2]);
});

test("exact character, section and page limits accepted", async () => {
  const large = await prepareDocumentParts({ text: "📚".repeat(200000) });
  assert.equal(large.total_characters, 200000);
  assert.equal(large.manifest.length, 9);
  assert.equal(large.manifest[8].end, 200000);
  assert.equal(
    (
      await prepareDocumentParts({
        text: "x".repeat(512),
        sectionCharacters: 1,
      })
    ).manifest.length,
    512,
  );
  assert.equal(
    (await prepareDocumentParts({ pages: Array(200).fill("") })).total_pages,
    200,
  );
});

test("exact raw code-point and UTF8 byte bounds accepted before normalization", async () => {
  assert.equal(
    (await prepareDocumentParts({ text: "\r\n".repeat(200000) }))
      .total_characters,
    200000,
  );
  const exact = "\u1100\u1161\u11a8".repeat(116508) + "xxxx";
  assert.equal(new TextEncoder().encode(exact).byteLength, 1024 * 1024);
  assert.equal(
    (await prepareDocumentParts({ text: exact })).total_characters,
    116512,
  );
  await assert.rejects(prepareDocumentParts({ text: exact + "x" }));
});

const invalid = [
  null,
  [],
  {},
  { text: "a", pages: [] },
  { text: "a", extra: true },
  { text: 1 },
  { text: null },
  { text: "\ud800" },
  { text: "\udfff" },
  { text: "PRIVATE\u0000TEXT" },
  { text: "x".repeat(200001) },
  { text: "\u0344".repeat(100001) },
  { text: "\r\n".repeat(200001) },
  { text: "\u1100\u1161\u11a8".repeat(116509) },
  { text: "x".repeat(513), sectionCharacters: 1 },
  ...[0, 24001, 1.5, true, "2", null, NaN, Infinity].map(
    (sectionCharacters) => ({ text: "a", sectionCharacters }),
  ),
  { pages: [] },
  { pages: Array(201).fill("") },
  { pages: ["a", null] },
  { pages: ["a", 1] },
  { pages: new Array(2) },
  { pages: ["\ud800"] },
  { pages: ["\u0000"] },
  { pages: ["a".repeat(100000), "b".repeat(100000)] },
];
for (const [index, input] of invalid.entries())
  test(`reject invalid/bounded input ${index} without source leakage`, async () => {
    await assert.rejects(prepareDocumentParts(input), {
      name: "TypeError",
      message: "Invalid document parts input",
    });
  });

test("reject accessor containers without executing source getters", async () => {
  let reads = 0;
  const input = {
    get text() {
      reads++;
      return "private";
    },
  };
  await assert.rejects(prepareDocumentParts(input));
  const pages = ["a"];
  Object.defineProperty(pages, 0, {
    get() {
      reads++;
      return "private";
    },
  });
  await assert.rejects(prepareDocumentParts({ pages }));
  assert.equal(reads, 0);
});

test("snapshot all pages and options before first asynchronous hash", async () => {
  const input = { pages: ["first", "last"], sectionCharacters: 3 };
  const promise = prepareDocumentParts(input);
  input.pages[0] = "changed";
  input.pages.splice(1, 1, "other", "extra");
  input.sectionCharacters = 1;
  const result = await promise;
  assert.equal(result.parts.map((p) => p.text).join(""), "first\nlast");
  assert.equal(result.total_pages, 2);
  assert.deepEqual(
    result.manifest.map((p) => p.page),
    [1, 1, 2, 2],
  );
  const second = await prepareDocumentParts({ text: "first" });
  result.parts[0].text = "changed result";
  assert.equal(second.parts[0].text, "first");
});

for (const trap of ["getPrototypeOf", "ownKeys", "getOwnPropertyDescriptor"]) {
  for (const pdf of [false, true]) {
    test(`proxy ${trap} error is redacted for ${pdf ? "PDF pages" : "input"}`, async () => {
      const target = pdf ? ["source"] : { text: "source" };
      const proxy = new Proxy(target, {
        [trap]() {
          throw new Error("SYNTHETIC_PRIVATE_SOURCE");
        },
      });
      await assert.rejects(
        prepareDocumentParts(pdf ? { pages: proxy } : proxy),
        (error) => {
          assert.equal(error.name, "TypeError");
          assert.equal(error.message, "Invalid document parts input");
          assert.equal(error.cause, undefined);
          assert.ok(!error.stack.includes("SYNTHETIC_PRIVATE_SOURCE"));
          return true;
        },
      );
    });
  }
}

test("revoked input/page proxies use the same fixed validation error", async () => {
  const input = Proxy.revocable({ text: "source" }, {});
  input.revoke();
  const pages = Proxy.revocable(["source"], {});
  pages.revoke();
  for (const value of [input.proxy, { pages: pages.proxy }]) {
    await assert.rejects(prepareDocumentParts(value), {
      name: "TypeError",
      message: "Invalid document parts input",
    });
  }
});

test("proxy-reported page length is validated without coercion", async () => {
  for (const length of [
    {
      valueOf() {
        throw new Error("SYNTHETIC_PRIVATE_SOURCE");
      },
    },
    1n,
  ]) {
    const pages = new Proxy(["source"], {
      getOwnPropertyDescriptor(target, key) {
        const descriptor = Reflect.getOwnPropertyDescriptor(target, key);
        return key === "length" ? { ...descriptor, value: length } : descriptor;
      },
    });
    await assert.rejects(prepareDocumentParts({ pages }), {
      name: "TypeError",
      message: "Invalid document parts input",
    });
  }
});
