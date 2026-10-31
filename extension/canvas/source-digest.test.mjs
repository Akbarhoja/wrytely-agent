import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { canonicalSourceBytes, sourceDigest } from "./source-digest.mjs";

// One owner-maintained fixture source; the extension must not fork the vectors.
const vectors = JSON.parse(
  await readFile(
    new URL("../../tests/fixtures/source_digest_v1.json", import.meta.url),
    "utf8",
  ),
);
const payload = () => structuredClone(vectors[0].input);
const text = (value) => new TextDecoder().decode(canonicalSourceBytes(value));

for (const vector of vectors) {
  test(`published Python bytes and SHA256: ${vector.name}`, async () => {
    assert.equal(text(vector.input), vector.canonical_utf8);
    assert.equal(await sourceDigest(vector.input), vector.sha256);
  });
}

test("NFC, line endings, offset dates and missing-set order share one digest", async () => {
  const first = payload();
  const second = payload();
  first.content = "Cafe\u0301\r\nLine 2\r";
  second.content = "Café\nLine 2\n";
  first.fields = { due_at: "2026-11-02T00:59:00.123456-05:00" };
  second.fields = { due_at: "2026-11-02T05:59:00.123456Z" };
  first.missing = ["rubric", "file", "rubric"];
  second.missing = ["file", "rubric"];
  assert.equal(await sourceDigest(first), await sourceDigest(second));
  assert.ok(text(first).includes("05:59:00.123456Z"));
});

test("numeric-looking and astral keys use Unicode scalar order", () => {
  const value = payload();
  value.fields = {
    2: "two",
    10: "ten",
    "\u{10000}": "astral",
    "\uE000": "bmp",
  };
  const serialized = text(value);
  assert.ok(
    serialized.includes(
      '"fields":{"10":"ten","2":"two","\uE000":"bmp","\u{10000}":"astral"}',
    ),
  );
});

test("body spacing and ordinary list order remain meaningful", async () => {
  const first = payload();
  first.fields = { rubric: ["one", "two"] };
  const second = structuredClone(first);
  second.fields.rubric.reverse();
  assert.notEqual(await sourceDigest(first), await sourceDigest(second));
  second.fields.rubric.reverse();
  second.content += " ";
  assert.notEqual(await sourceDigest(first), await sourceDigest(second));
});

test("normalization never mutates its caller's observation", async () => {
  const value = payload();
  value.missing = ["z", "a", "z"];
  value.fields.due_at = "2026-11-01T23:59:00-06:00";
  const original = structuredClone(value);
  await sourceDigest(value);
  assert.deepEqual(value, original);
});

test("unknown metadata cannot enter the content digest", () => {
  for (const key of [
    "user_id",
    "observed_at",
    "reference",
    "provider_updated_at",
  ]) {
    assert.throws(() =>
      canonicalSourceBytes({ ...payload(), [key]: "not-content" }),
    );
  }
});

for (const invalid of [
  1.25,
  NaN,
  Infinity,
  2 ** 53,
  undefined,
  1n,
  new Date(0),
  () => null,
]) {
  test(`nonportable values reject: ${String(invalid)}`, () => {
    const value = payload();
    value.fields = { nested: invalid };
    assert.throws(() => canonicalSourceBytes(value));
  });
}

test("normalized key collisions and lone Unicode surrogates reject", () => {
  const value = payload();
  value.fields = { é: 1, "e\u0301": 2 };
  assert.throws(() => canonicalSourceBytes(value));
  for (const invalid of ["\ud800", "\udfff", "a\ud800b"]) {
    value.fields = {};
    value.content = invalid;
    assert.throws(() => canonicalSourceBytes(value));
  }
});

test("depth and UTF-8 byte limits reject instead of clipping evidence", () => {
  const value = payload();
  let nested = null;
  for (let i = 0; i < 17; i++) nested = [nested];
  value.fields = { nested };
  assert.throws(() => canonicalSourceBytes(value));
  value.fields = {};
  value.content = "é".repeat(524288);
  assert.throws(() => canonicalSourceBytes(value));
});

for (const invalid of [
  "2026-11-02",
  "2026-11-02T05:59:00",
  "tomorrow",
  true,
  "2026-02-30T00:00:00Z",
  "2026-01-01T00:00:00.1234567Z",
  "0000-01-01T00:00:00Z",
  "2026-01-01T00:00:00+01:60",
  "2026-01-01T00:00:00+24:00",
]) {
  test(`invalid date rejects: ${invalid}`, () => {
    const value = payload();
    value.fields = { due_at: invalid };
    assert.throws(() => canonicalSourceBytes(value));
  });
}

test("early years, leap days and UTC day rollover preserve microseconds", () => {
  for (const [input, expected] of [
    ["0001-01-01T00:00:00.1Z", "0001-01-01T00:00:00.100000Z"],
    ["2024-02-29T23:30:00.123456-01:00", "2024-03-01T00:30:00.123456Z"],
    ["2026-01-01T00:30:00+01:00", "2025-12-31T23:30:00.000000Z"],
  ]) {
    const value = payload();
    value.fields = { due_at: input };
    assert.ok(text(value).includes(expected));
  }
});

test("prototype-sensitive keys serialize as evidence without prototype mutation", () => {
  const value = payload();
  value.fields = JSON.parse(
    '{"__proto__":{"safe":true},"constructor":"source-text"}',
  );
  assert.ok(text(value).includes('"__proto__":{"safe":true}'));
  assert.equal({}.safe, undefined);
});
