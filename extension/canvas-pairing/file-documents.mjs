// Browser-only bounded file download. Signed URLs and bytes never enter the journal.
import { ProbeError, nextLink } from "../canvas-feasibility/probe.mjs";
import { readStorageFile } from "./file-storage.mjs";
const supported = new Set([
  "application/pdf",
  "text/plain",
  "text/html",
  "text/x-c",
  "text/x-csrc",
]);
const id = (x) => {
  if (
    !["string", "number"].includes(typeof x) ||
    (typeof x === "number" && !Number.isSafeInteger(x)) ||
    !/^[1-9][0-9]{0,19}$/.test(String(x))
  )
    throw new ProbeError("invalid_collection");
  return String(x);
};
const base64 = (bytes) => {
  let s = "";
  for (let i = 0; i < bytes.length; i += 8192)
    s += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(s);
};
export async function readFilePage({
  course,
  cursor,
  origin,
  get,
  transport,
  identity,
}) {
  const path = `/api/v1/courses/${course}/files`;
  function checked(value) {
    try {
      if (
        typeof value !== "string" ||
        value.length > 4000 ||
        /[\u0000-\u0020\u007f]/u.test(value)
      )
        throw Error();
      const u = new URL(value);
      if (
        u.origin !== origin ||
        u.pathname !== path ||
        u.username ||
        u.password ||
        u.hash ||
        [...u.searchParams.keys()].some(
          (k) => !["per_page", "page"].includes(k),
        ) ||
        ["per_page", "page"].some((k) => u.searchParams.getAll(k).length > 1) ||
        u.searchParams.get("per_page") !== "4" ||
        (u.searchParams.has("page") && !u.searchParams.get("page"))
      )
        throw Error();
      return u;
    } catch {
      throw new ProbeError("unsafe_pagination");
    }
  }
  const u = checked(cursor ?? `${origin}${path}?per_page=4`);
  let listed;
  try {
    listed = await get(path, u.search);
  } catch (e) {
    if (e?.code === "permission_denied")
      throw Object.assign(new ProbeError("permission_denied"), {
        fileListingDenied: true,
      });
    throw e;
  }
  const { data, link } = listed;
  if (
    !Array.isArray(data) ||
    data.length > 4 ||
    new TextEncoder().encode(link).length > 16384
  )
    throw new ProbeError("invalid_collection");
  const result = await readFileObjects({
    course,
    items: data,
    origin,
    get,
    transport,
    identity,
  });
  const next = nextLink(link),
    next_cursor = next === null ? null : checked(next).href;
  if (next_cursor === u.href) throw new ProbeError("pagination_cycle");
  return { data: result, next_cursor };
}
export async function readFileObjects({
  course,
  items,
  origin,
  get,
  transport,
  identity,
}) {
  const path = `/api/v1/courses/${course}/files`;
  const seen = new Set(),
    result = [];
  for (const item of items) {
    const fileId = id(item?.id);
    if (seen.has(fileId)) throw new ProbeError("invalid_collection");
    seen.add(fileId);
    const raw = (await get(`${path}/${fileId}`)).data;
    if (!raw || id(raw.id) !== fileId)
      throw new ProbeError("invalid_collection");
    const contentType = raw["content-type"];
    if (
      typeof contentType !== "string" ||
      !/^[a-z0-9.+-]{1,64}\/[a-z0-9.+-]{1,128}$/.test(contentType)
    )
      throw new ProbeError("invalid_collection");
    let encoded = null,
      gap = null;
    if (raw.locked_for_user === true || raw.hidden_for_user === true)
      gap = "file_restricted";
    else if (!supported.has(contentType)) gap = "unsupported_format";
    else if (Number(raw.size) > 5 * 1024 * 1024) gap = "file_size_limit";
    else {
      let url;
      try {
        url = new URL(raw.url);
      } catch {
        throw new ProbeError("unsafe_file_url");
      }
      if (url.origin === origin) {
        if (
          url.pathname !== `/files/${fileId}/download` ||
          url.username ||
          url.password ||
          url.hash ||
          [...url.searchParams.keys()].some((k) => k !== "download_frd") ||
          url.searchParams.getAll("download_frd").length > 1 ||
          (url.searchParams.has("download_frd") &&
            url.searchParams.get("download_frd") !== "1")
        )
          throw new ProbeError("unsafe_file_url");
        url = new URL(
          (await get(`/api/v1/files/${fileId}/public_url`)).data.public_url,
        );
      }
      try {
        encoded = base64(
          await readStorageFile({
            url: url.href,
            contentType,
            transport,
            identity,
          }),
        );
      } catch (error) {
        if (
          ![
            "permission_denied",
            "file_size_limit",
            "file_type_mismatch",
            "invalid_pdf_signature",
          ].includes(error?.code)
        )
          throw error;
        gap = error.code;
      }
    }
    result.push({
      id: fileId,
      filename: raw.filename,
      updated_at: raw.updated_at ?? null,
      _wrytely_file: { contentType, encoded, gap },
    });
  }
  return result;
}
export async function prepareFileDocuments({
  resource_key,
  page,
  origin,
  extractFile,
}) {
  const course = resource_key.split("/")[0],
    documents = [];
  for (const raw of page.data) {
    const file = raw._wrytely_file;
    let converted;
    if (file.encoded === null)
      converted = {
        schema_version: 2,
        extractor_version: "canvas.text.v1",
        source: { text: "" },
        coverage: !supported.has(file.contentType) ? "unsupported" : "partial",
        missing: [
          ...new Set([
            file.gap,
            ...(!supported.has(file.contentType) ? ["unsupported_format"] : []),
          ]),
        ].sort(),
      };
    else
      converted = await extractFile(
        course,
        id(raw.id),
        file.contentType,
        file.encoded,
      );
    if (
      converted?.schema_version !== 2 ||
      ![
        "canvas.pdf.v1",
        "canvas.html.v1",
        "canvas.html.v2",
        "canvas.text.v1",
      ].includes(converted.extractor_version) ||
      !["complete", "partial", "unsupported"].includes(converted.coverage) ||
      !Array.isArray(converted.missing) ||
      !converted.source
    )
      throw new ProbeError("invalid_collection");
    const filename =
      typeof raw.filename === "string"
        ? raw.filename.split(/[\\/]/).at(-1)
        : null;
    if (!filename || [...filename.normalize("NFC")].length > 300)
      throw new ProbeError("invalid_collection");
    documents.push({
      owner_object: { kind: "file", provider_id: id(raw.id) },
      object_fields: {
        filename,
        content_type: file.contentType,
        ...(raw._wrytely_linked_from
          ? { linked_from: raw._wrytely_linked_from }
          : {}),
      },
      metadata: {
        title: filename,
        format:
          "pages" in converted.source
            ? "pdf_text"
            : ["canvas.html.v1", "canvas.html.v2"].includes(
                  converted.extractor_version,
                )
              ? "html_text"
              : "text",
        extractor_version: converted.extractor_version,
        provider_updated_at: raw.updated_at,
        coverage: converted.coverage,
        missing: converted.missing,
      },
      source: converted.source,
      reference: `${origin}/courses/${course}/files/${id(raw.id)}`,
    });
  }
  return {
    resource_key,
    observed_at: new Date().toISOString(),
    documents,
    next_cursor: page.next_cursor,
    coverage: {
      state: page.next_cursor
        ? "partial"
        : (page.coverage?.state ?? "complete"),
      reason: page.next_cursor ? "more_pages" : (page.coverage?.reason ?? null),
    },
  };
}
