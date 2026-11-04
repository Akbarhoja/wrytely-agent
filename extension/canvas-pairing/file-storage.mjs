// Reuses the P0-validated one-request redirect observer; no URL/header logging.
import { ProbeError } from "../canvas-feasibility/probe.mjs";
export const FILE_ORIGIN = "https://inst-fs-iad-prod.inscloudgate.net";
export const CDN_ORIGIN = "https://cdn.inst-fs-iad-prod.inscloudgate.net";
const cancel = async (body) => {
  try {
    await body?.cancel();
  } catch {
    /* Preserve the original classification. */
  }
};

function storageURL(value, contentType, cdnOnly = false) {
  try {
    const u = new URL(value);
    if (
      (cdnOnly
        ? u.origin !== CDN_ORIGIN
        : ![FILE_ORIGIN, CDN_ORIGIN].includes(u.origin)) ||
      u.username ||
      u.password ||
      u.hash ||
      u.href.length > 16384 ||
      decodeURIComponent(u.pathname)
        .split("/")
        .some((x) => x === ".." || x === ".") ||
      (u.origin === FILE_ORIGIN && !u.pathname.startsWith("/files/"))
    )
      throw Error();
    if (
      u.origin === CDN_ORIGIN &&
      (!/^\/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\/[^/]+$/i.test(
        u.pathname,
      ) ||
        decodeURIComponent(u.pathname).split("/").length !== 3 ||
        [...u.searchParams.keys()].some(
          (x) => !["token", "content_type"].includes(x),
        ) ||
        u.searchParams.getAll("token").length !== 1 ||
        !u.searchParams.get("token") ||
        u.searchParams.getAll("content_type").length !== 1 ||
        u.searchParams.get("content_type") !== contentType)
    )
      throw Error();
    return u;
  } catch {
    throw new ProbeError("unsafe_file_url");
  }
}
export async function readStorageFile({
  url,
  contentType,
  transport = { fetch, location: () => null },
  identity,
}) {
  let target = storageURL(url, contentType),
    response;
  for (let hop = 0; hop < 2; hop++) {
    await identity();
    try {
      response = await transport.fetch(target.href, {
        method: "GET",
        credentials: "omit",
        redirect: "manual",
        cache: "no-store",
        referrerPolicy: "no-referrer",
        headers: { Accept: contentType },
        signal: AbortSignal.timeout(15000),
      });
    } catch {
      throw new ProbeError("file_network_failed");
    }
    if (response.url && response.url !== target.href) {
      await cancel(response.body);
      throw new ProbeError("unsafe_file_redirect");
    }
    if (
      response.type === "opaqueredirect" ||
      (response.status >= 300 && response.status < 400)
    ) {
      await cancel(response.body);
      if (hop || target.origin !== FILE_ORIGIN)
        throw new ProbeError("unsafe_file_redirect");
      target = storageURL(transport.location(response), contentType, true);
      continue;
    }
    break;
  }
  if (!response.ok) {
    await cancel(response.body);
    throw new ProbeError(
      response.status === 403 ? "permission_denied" : "file_access_failed",
    );
  }
  if (
    response.headers
      .get("content-type")
      ?.split(";", 1)[0]
      .trim()
      .toLowerCase() !== contentType
  ) {
    await cancel(response.body);
    throw new ProbeError("file_type_mismatch");
  }
  const limit = 5 * 1024 * 1024,
    size = response.headers.get("content-length");
  if (size && (!/^\d+$/.test(size) || Number(size) > limit)) {
    await cancel(response.body);
    throw new ProbeError("file_size_limit");
  }
  const reader = response.body?.getReader();
  if (!reader) throw new ProbeError("invalid_response");
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > limit) throw new ProbeError("file_size_limit");
      chunks.push(value);
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      /* Preserve read/limit errors. */
    }
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  if (
    contentType === "application/pdf" &&
    new TextDecoder().decode(bytes.slice(0, 5)) !== "%PDF-"
  )
    throw new ProbeError("invalid_pdf_signature");
  await identity();
  return bytes;
}
export function makeFileTransport(
  webRequest,
  extensionOrigin,
  fetchImpl = fetch,
) {
  const locations = new WeakMap();
  return {
    location: (response) => locations.get(response) ?? null,
    fetch: async (url, options) => {
      if (new URL(url).origin !== FILE_ORIGIN) return fetchImpl(url, options);
      let finish, timer;
      const headers = new Promise((resolve) => {
        finish = resolve;
      });
      const listener = (event) => {
        if (
          event.url !== url ||
          event.initiator !== extensionOrigin ||
          event.method !== "GET"
        )
          return;
        const values = (event.responseHeaders ?? []).filter(
          (h) => h.name.toLowerCase() === "location",
        );
        finish(
          [301, 302, 303, 307, 308].includes(event.statusCode) &&
            values.length === 1 &&
            typeof values[0].value === "string"
            ? values[0].value
            : null,
        );
      };
      webRequest.onHeadersReceived.addListener(
        listener,
        { urls: [`${FILE_ORIGIN}/files/*`], types: ["xmlhttprequest"] },
        ["responseHeaders"],
      );
      try {
        const response = await fetchImpl(url, options);
        if (
          response.type === "opaqueredirect" ||
          (response.status >= 300 && response.status < 400)
        ) {
          timer = setTimeout(() => finish(null), 1000);
          const location = await headers;
          if (location) locations.set(response, location);
        }
        return response;
      } finally {
        clearTimeout(timer);
        webRequest.onHeadersReceived.removeListener(listener);
      }
    },
  };
}
