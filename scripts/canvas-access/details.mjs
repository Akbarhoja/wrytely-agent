// P0 operator diagnostic. In-memory source reads; only fixed classifications/counts leave.
import {
  checkedOrigin,
  makeReader,
  ProbeError,
  probeCanvas,
} from "./probe.mjs";

export const FILE_ORIGIN = "https://inst-fs-iad-prod.inscloudgate.net";
export const MAX_PDF_BYTES = 5 * 1024 * 1024;
const numeric = (value) => {
  if (typeof value !== "string" || !/^[1-9][0-9]{0,19}$/.test(value))
    throw new ProbeError("invalid_detail_scope");
  return value;
};

export function validateScope(config) {
  const origin = checkedOrigin(config.origin);
  if (
    !Array.isArray(config.courseIds) ||
    !config.courseIds.length ||
    config.courseIds.length > 2
  )
    throw new ProbeError("invalid_detail_scope");
  const courses = config.courseIds.map(numeric);
  if (
    new Set(courses).size !== courses.length ||
    !Array.isArray(config.fileSamples) ||
    config.fileSamples.length > 1
  )
    throw new ProbeError("invalid_detail_scope");
  for (const sample of config.fileSamples) {
    if (
      !sample ||
      !courses.includes(numeric(sample.courseId)) ||
      !numeric(sample.fileId) ||
      !/^[a-f0-9]{64}$/.test(sample.expectedSha256)
    )
      throw new ProbeError("invalid_detail_scope");
  }
  return { origin, courses };
}

function checkFileScope(metadata, sample) {
  if (
    String(metadata?.id) !== sample.fileId ||
    metadata.locked_for_user === true ||
    metadata.hidden_for_user === true
  )
    throw new ProbeError("file_scope_or_access_denied");
}

export async function resolvePdfMetadata(api, metadata, sample, origin) {
  checkFileScope(metadata, sample);
  let url;
  try {
    url = new URL(metadata.url);
  } catch {
    throw new ProbeError("unsafe_file_url");
  }
  if (url.origin !== origin) return metadata; // Direct storage URLs still face readPdf's exact allowlist.
  if (
    url.username ||
    url.password ||
    url.hash ||
    url.pathname !== `/files/${sample.fileId}/download` ||
    [...url.searchParams.keys()].some((k) => k !== "download_frd") ||
    (url.searchParams.has("download_frd") &&
      url.searchParams.get("download_frd") !== "1") ||
    url.searchParams.getAll("download_frd").length > 1
  )
    throw new ProbeError("unsafe_file_url");
  // Resolve the known Canvas download wrapper through its documented read-only API.
  // Never follow arbitrary redirects or emit this signed URL in diagnostics.
  const { data } = await api.get(`/api/v1/files/${sample.fileId}/public_url`);
  return { ...metadata, url: data.public_url };
}

export async function readPdf(metadata, sample, fetchImpl = fetch) {
  checkFileScope(metadata, sample);
  let url;
  try {
    url = new URL(metadata.url);
  } catch {
    throw new ProbeError("unsafe_file_url");
  }
  if (
    url.origin !== FILE_ORIGIN ||
    url.username ||
    url.password ||
    url.hash ||
    !url.pathname.startsWith("/files/") ||
    url.href.length > 16384
  )
    throw new ProbeError("unsafe_file_url");
  let response;
  try {
    response = await fetchImpl(url.href, {
      method: "GET",
      credentials: "omit",
      redirect: "error",
      cache: "no-store",
      referrerPolicy: "no-referrer",
      headers: { Accept: "application/pdf" },
      signal: AbortSignal.timeout(15000),
    });
  } catch {
    throw new ProbeError("file_network_or_redirect_blocked");
  }
  const cancel = async () => {
    await response.body?.cancel();
  };
  if (!response.ok) {
    await cancel();
    throw new ProbeError("file_access_failed");
  }
  if (response.url && response.url !== url.href) {
    await cancel();
    throw new ProbeError("file_redirect_blocked");
  }
  if (
    !/^application\/pdf(?:;|$)/i.test(
      response.headers.get("content-type") ?? "",
    )
  ) {
    await cancel();
    throw new ProbeError("file_not_pdf");
  }
  const length = response.headers.get("content-length");
  if (length && (!/^\d+$/.test(length) || Number(length) > MAX_PDF_BYTES)) {
    await cancel();
    throw new ProbeError("file_size_limit");
  }
  const reader = response.body?.getReader();
  if (!reader) throw new ProbeError("invalid_file_response");
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_PDF_BYTES) throw new ProbeError("file_size_limit");
      chunks.push(value);
    }
  } finally {
    await reader.cancel();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  if (new TextDecoder().decode(bytes.slice(0, 5)) !== "%PDF-")
    throw new ProbeError("file_invalid_signature");
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  const hash = [...digest].map((x) => x.toString(16).padStart(2, "0")).join("");
  return {
    state: "read",
    byteLength: size,
    pdfSignature: true,
    matchesOperatorSample: hash === sample.expectedSha256,
    textExtraction: "separate_local_sample_only",
  };
}

export async function probeDetails(config, fetchImpl = fetch) {
  const { origin, courses } = validateScope(config);
  const api = makeReader(origin, fetchImpl);
  const initial = String((await api.get("/api/v1/users/self/profile")).data.id);
  if (!/^[1-9][0-9]*$/.test(initial))
    throw new ProbeError("invalid_provider_id");
  const identity = async () => {
    if (
      String((await api.get("/api/v1/users/self/profile")).data.id) !== initial
    )
      throw new ProbeError("account_switched_discarded");
  };
  const report = await probeCanvas(config, fetchImpl);
  await identity();
  for (const [index, course] of courses.entries()) {
    const resources = report.courses[index].resources;
    const resource = async (name, operation) => {
      await identity();
      try {
        resources[name] = await operation();
      } catch (error) {
        resources[name] = {
          state: "incomplete",
          reason:
            error instanceof ProbeError ? error.code : "detail_probe_failed",
        };
      }
      await identity(); // An account change discards even previously successful results.
    };
    await resource("rubricDetails", async () => {
      const assignments = await api.list(
        `/api/v1/courses/${course}/assignments`,
      );
      const candidates = assignments.filter(
        (a) =>
          (Array.isArray(a?.rubric) && a.rubric.length) || a?.rubric_settings,
      );
      const chosen = (candidates.length ? candidates : assignments).slice(0, 2);
      let withRubric = 0,
        criteria = 0,
        detailsRead = 0;
      for (const item of chosen) {
        await identity();
        const id = numeric(String(item.id));
        const { data } = await api.get(
          `/api/v1/courses/${course}/assignments/${id}`,
        );
        if (String(data.id) !== id)
          throw new ProbeError("assignment_identity_mismatch");
        detailsRead++;
        if (Array.isArray(data.rubric) && data.rubric.length) {
          if (
            data.rubric.length > 200 ||
            data.rubric.some(
              (c) =>
                !c ||
                typeof c.description !== "string" ||
                !c.description.trim(),
            )
          )
            throw new ProbeError("invalid_rubric");
          withRubric++;
          criteria += data.rubric.length;
        }
        await identity();
      }
      return {
        state: "read",
        assignmentsListed: assignments.length,
        detailsRead,
        withRubric,
        criteria,
        coverage: withRubric
          ? "bounded_positive_sample"
          : "no_rubric_observed_in_sample",
      };
    });
    const sample = config.fileSamples.find((s) => s.courseId === course);
    if (sample)
      await resource("linkedPdf", async () => {
        const { data } = await api.get(
          `/api/v1/courses/${course}/files/${sample.fileId}`,
        );
        await identity();
        const resolved = await resolvePdfMetadata(api, data, sample, origin);
        await identity();
        return readPdf(resolved, sample, fetchImpl);
      });
  }
  await identity();
  return { ...report, diagnosticVersion: 3 };
}
