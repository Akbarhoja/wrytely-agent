// Pure preparation of already-extracted text. No IO, coverage or authorization.
const ENCODER = new TextEncoder();
const MAX_CHARACTERS = 200000;
const MAX_RAW_CHARACTERS = 400000;
const MAX_BYTES = 1024 * 1024;
const MAX_SECTIONS = 512;
const MAX_SECTION_CHARACTERS = 24000;
const MAX_PAGES = 200;

function invalid() {
  throw new TypeError("Invalid document parts input");
}

function properties(value, prototype, array = false) {
  try {
    if (
      value === null ||
      typeof value !== "object" ||
      (array && !Array.isArray(value)) ||
      !prototype.includes(Object.getPrototypeOf(value))
    )
      invalid();
    const fields = Object.getOwnPropertyDescriptors(value);
    if (
      Reflect.ownKeys(fields).some(
        (key) => typeof key !== "string" || !("value" in fields[key]),
      )
    )
      invalid();
    return fields;
  } catch {
    // Container reflection can execute proxy traps. Never propagate their data.
    invalid();
  }
}

export async function prepareDocumentParts(input) {
  const fields = properties(input, [Object.prototype, null]);
  const keys = Object.keys(fields);
  const pdf = Object.hasOwn(fields, "pages");
  const source = pdf ? "pages" : "text";
  if (
    !Object.hasOwn(fields, source) ||
    keys.some((key) => ![source, "sectionCharacters"].includes(key))
  )
    invalid();
  const size = fields.sectionCharacters?.value ?? MAX_SECTION_CHARACTERS;
  // Explicit null is not an omitted option.
  if (
    Object.hasOwn(fields, "sectionCharacters") &&
    fields.sectionCharacters.value == null
  )
    invalid();
  if (!Number.isInteger(size) || size < 1 || size > MAX_SECTION_CHARACTERS)
    invalid();
  let raw;
  if (pdf) {
    const pages = fields.pages.value;
    const entries = properties(pages, [Array.prototype], true);
    const count = entries.length.value;
    if (
      !Number.isInteger(count) ||
      count < 1 ||
      count > MAX_PAGES ||
      Object.keys(entries).length !== count + 1
    )
      invalid();
    raw = Array.from({ length: count }, (_, index) => {
      if (!Object.hasOwn(entries, index)) invalid();
      return entries[index].value;
    });
  } else {
    raw = [fields.text.value];
  }

  // Snapshot, validate and normalize everything before the first asynchronous hash.
  let rawCharacters = 0;
  let rawBytes = 0;
  const normalized = raw.map((text) => {
    if (typeof text !== "string" || text.length > 2 * MAX_RAW_CHARACTERS)
      invalid();
    for (const character of text) {
      const point = character.codePointAt(0);
      rawCharacters++;
      if (
        point === 0 ||
        (point >= 0xd800 && point <= 0xdfff) ||
        rawCharacters > MAX_RAW_CHARACTERS
      )
        invalid();
    }
    rawBytes += ENCODER.encode(text).byteLength;
    if (rawBytes > MAX_BYTES) invalid();
    return text.replace(/\r\n?/g, "\n").normalize("NFC");
  });
  const parts = [];
  const manifest = [];
  const unrepresented = [];
  let total = 0;
  for (const [index, text] of normalized.entries()) {
    if (!text) {
      if (pdf) unrepresented.push(index + 1);
      continue;
    }
    const points = Array.from((pdf && total ? "\n" : "") + text);
    if (total + points.length > MAX_CHARACTERS) invalid();
    for (let start = 0; start < points.length; start += size) {
      if (parts.length >= MAX_SECTIONS) invalid();
      const content = points.slice(start, start + size).join("");
      const length = Math.min(size, points.length - start);
      const slot = parts.length;
      parts.push({ slot, text: content });
      manifest.push({
        slot,
        start: total,
        end: total + length,
        page: pdf ? index + 1 : null,
      });
      total += length;
    }
  }
  const hashes = await Promise.all(
    parts.map(async (part) => {
      const digest = await globalThis.crypto.subtle.digest(
        "SHA-256",
        ENCODER.encode(part.text),
      );
      return Array.from(new Uint8Array(digest), (byte) =>
        byte.toString(16).padStart(2, "0"),
      ).join("");
    }),
  );
  return {
    manifest: manifest.map((slot, index) => ({
      ...slot,
      text_sha256: hashes[index],
    })),
    parts,
    total_characters: total,
    total_pages: pdf ? raw.length : null,
    unrepresented_pages: unrepresented,
  };
}
