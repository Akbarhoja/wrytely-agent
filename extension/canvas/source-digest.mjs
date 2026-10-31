// Browser-side C2 v1 compatibility helper. No fetch, credentials or ingestion IO.
const KEYS = new Set([
  "digest_version",
  "kind",
  "title",
  "content",
  "fields",
  "coverage",
  "missing",
]);
const DATES = new Set([
  "due_at",
  "unlock_at",
  "lock_at",
  "submitted_at",
  "sent_at",
]);
const COVERAGE = new Set(["complete", "partial", "restricted", "unsupported"]);

function invalid() {
  throw new TypeError("Invalid C2 digest input");
}

function isObject(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    [Object.prototype, null].includes(Object.getPrototypeOf(value))
  );
}

function normalizedText(value) {
  for (const character of value) {
    const point = character.codePointAt(0);
    if (point >= 0xd800 && point <= 0xdfff) invalid();
  }
  return value.replace(/\r\n?/g, "\n").normalize("NFC");
}

// Python sorts strings by Unicode scalar, not JavaScript's UTF-16 code units.
function compareKeys(first, second) {
  const a = Array.from(first, (character) => character.codePointAt(0));
  const b = Array.from(second, (character) => character.codePointAt(0));
  for (let index = 0; index < Math.min(a.length, b.length); index++) {
    if (a[index] !== b[index]) return a[index] - b[index];
  }
  return a.length - b.length;
}

function normalizedDate(value) {
  if (typeof value !== "string") invalid();
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/.exec(
      value,
    );
  if (!match || match[0] !== value) invalid();
  const [
    ,
    yearText,
    monthText,
    dayText,
    hourText,
    minuteText,
    secondText,
    fraction,
    offset,
  ] = match;
  const [year, month, day, hour, minute, second] = [
    yearText,
    monthText,
    dayText,
    hourText,
    minuteText,
    secondText,
  ].map(Number);
  if (
    year < 1 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > 31 ||
    hour > 23 ||
    minute > 59 ||
    second > 59
  )
    invalid();
  const date = new Date(0);
  // Date.UTC interprets years 0–99 as 1900–1999; setUTCFullYear preserves the source year.
  date.setUTCFullYear(year, month - 1, day);
  date.setUTCHours(hour, minute, second, 0);
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  )
    invalid();
  if (offset !== "Z") {
    const hours = Number(offset.slice(1, 3));
    const minutes = Number(offset.slice(4, 6));
    if (hours > 23 || minutes > 59) invalid();
    date.setTime(
      date.getTime() -
        (offset[0] === "+" ? 1 : -1) * (hours * 60 + minutes) * 60000,
    );
  }
  if (date.getUTCFullYear() < 1 || date.getUTCFullYear() > 9999) invalid();
  // Offset conversion moves whole minutes; preserve all six fractional digits separately.
  return (
    date.toISOString().slice(0, 19) +
    "." +
    (fraction ?? "").padEnd(6, "0") +
    "Z"
  );
}

function normalize(value, depth = 0) {
  if (depth > 16) invalid();
  if (value === null || typeof value === "boolean") return value;
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) invalid();
    return value;
  }
  if (typeof value === "string") return normalizedText(value);
  if (Array.isArray(value)) {
    // Sparse arrays must not silently turn absent evidence into JSON null.
    for (let index = 0; index < value.length; index++) {
      if (!Object.hasOwn(value, index)) invalid();
    }
    return value.map((item) => normalize(item, depth + 1));
  }
  if (!isObject(value) || Object.getOwnPropertySymbols(value).length) invalid();
  const result = Object.create(null);
  for (const original of Object.keys(value)) {
    const key = normalizedText(original);
    if (Object.hasOwn(result, key)) invalid();
    const descriptor = Object.getOwnPropertyDescriptor(value, original);
    if (!Object.hasOwn(descriptor, "value")) invalid();
    let item = descriptor.value;
    if (DATES.has(key) && item !== null) item = normalizedDate(item);
    result[key] = normalize(item, depth + 1);
  }
  return result;
}

function encode(value) {
  if (Array.isArray(value)) return "[" + value.map(encode).join(",") + "]";
  if (value !== null && typeof value === "object") {
    // JSON.stringify reorders numeric-looking keys even after insertion sorting.
    return (
      "{" +
      Object.keys(value)
        .sort(compareKeys)
        .map((key) => JSON.stringify(key) + ":" + encode(value[key]))
        .join(",") +
      "}"
    );
  }
  return JSON.stringify(value);
}

export function canonicalSourceBytes(payload) {
  if (
    !isObject(payload) ||
    Object.keys(payload).length !== KEYS.size ||
    Object.keys(payload).some((key) => !KEYS.has(key)) ||
    payload.digest_version !== 1
  )
    invalid();
  for (const key of ["kind", "title", "content", "coverage"]) {
    if (typeof payload[key] !== "string") invalid();
  }
  if (
    !payload.kind ||
    !COVERAGE.has(payload.coverage) ||
    !isObject(payload.fields) ||
    !Array.isArray(payload.missing) ||
    payload.missing.some((item) => typeof item !== "string")
  )
    invalid();
  const normalized = normalize(payload);
  normalized.missing = [...new Set(normalized.missing)].sort(compareKeys);
  const bytes = new TextEncoder().encode(encode(normalized));
  if (bytes.byteLength > 1024 * 1024) invalid();
  return bytes;
}

export async function sourceDigest(payload) {
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    canonicalSourceBytes(payload),
  );
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}
