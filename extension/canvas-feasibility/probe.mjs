// P0-M1 diagnostic only. No persistence of source content and no Wrytely upload.
export class ProbeError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

export function checkedOrigin(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new ProbeError("invalid_origin");
  }
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    url.port ||
    url.pathname !== "/" ||
    url.search ||
    url.hash ||
    !url.hostname.includes(".") ||
    !/^[a-z0-9.-]+$/i.test(url.hostname)
  )
    throw new ProbeError("invalid_origin");
  return url.origin;
}

function safeURL(value, origin, path) {
  const url = new URL(value, origin);
  if (
    url.origin !== origin ||
    url.username ||
    url.password ||
    url.hash ||
    url.pathname !== path ||
    [...url.searchParams.keys()].some((k) => /token|password/i.test(k))
  ) {
    throw new ProbeError("unsafe_pagination");
  }
  return url.href;
}

async function boundedText(response, maxBytes) {
  if (Number(response.headers.get("content-length")) > maxBytes) {
    await response.body?.cancel();
    throw new ProbeError("size_limit");
  }
  const reader = response.body?.getReader();
  if (!reader) throw new ProbeError("invalid_response");
  const chunks = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > maxBytes) throw new ProbeError("size_limit");
      chunks.push(value);
    }
  } finally {
    await reader.cancel();
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(bytes);
}

export function makeReader(originValue, fetchImpl = fetch, maxPages = 10) {
  const origin = checkedOrigin(originValue);
  async function get(path, query = "") {
    const url = safeURL(path + query, origin, path);
    return read(url);
  }
  async function read(url) {
    let response;
    try {
      response = await fetchImpl(url, {
        method: "GET",
        credentials: "include",
        redirect: "error",
        cache: "no-store",
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(15000),
      });
    } catch {
      throw new ProbeError("network_or_redirect_blocked");
    }
    if (!response.ok) {
      await response.body?.cancel();
      throw new ProbeError(
        {
          401: "login_required",
          403: "permission_denied",
          404: "not_found",
          429: "rate_limited",
          503: "provider_unavailable",
        }[response.status] ?? "provider_error",
      );
    }
    if (
      !/^application\/json(?:;|$)/i.test(
        response.headers.get("content-type") ?? "",
      )
    ) {
      await response.body?.cancel();
      throw new ProbeError("login_or_non_json");
    }
    let data;
    try {
      data = JSON.parse(await boundedText(response, 1024 * 1024));
    } catch (error) {
      throw error instanceof ProbeError
        ? error
        : new ProbeError("invalid_json");
    }
    return { data, link: response.headers.get("link") ?? "" };
  }
  async function list(path, query = "?per_page=50") {
    let next = safeURL(path + query, origin, path);
    const seen = new Set();
    const items = [];
    while (next) {
      if (seen.has(next)) throw new ProbeError("pagination_cycle");
      if (seen.size >= maxPages) throw new ProbeError("page_limit");
      seen.add(next);
      const { data, link } = await read(next);
      if (!Array.isArray(data)) throw new ProbeError("invalid_collection");
      items.push(...data);
      // Consume the whole header: recognizing one valid relation must not hide
      // an unparseable next page. Commas inside an opaque URL are preserved.
      const links = link
        ? link.split(/,(?=\s*<)/).map((part) => {
            const match = part.match(/^\s*<([^>]+)>\s*;\s*rel="([^"]+)"\s*$/);
            if (!match) throw new ProbeError("invalid_pagination");
            return match;
          })
        : [];
      const following = links.filter((x) => x[2].split(/\s+/).includes("next"));
      if (following.length > 1) throw new ProbeError("invalid_pagination");
      next = following.length ? safeURL(following[0][1], origin, path) : null;
    }
    return items;
  }
  return { get, list };
}

const id = (value) => {
  if (typeof value === "number" && !Number.isSafeInteger(value)) {
    throw new ProbeError("invalid_provider_id");
  }
  if (!/^[1-9][0-9]*$/.test(String(value)))
    throw new ProbeError("invalid_provider_id");
  return String(value);
};

export async function probeCanvas(config, fetchImpl = fetch) {
  const api = makeReader(config.origin, fetchImpl);
  if (
    !Array.isArray(config.courseIds) ||
    config.courseIds.length === 0 ||
    config.courseIds.length > 2
  )
    throw new ProbeError("select_one_or_two_consenting_courses");
  const selected = [...new Set(config.courseIds.map(id))];
  const subject = id((await api.get("/api/v1/users/self/profile")).data.id);
  const checkIdentity = async () => {
    if (id((await api.get("/api/v1/users/self/profile")).data.id) !== subject) {
      throw new ProbeError("account_switched_discarded");
    }
  };
  // Discover all accessible courses, but read contents only for explicitly selected scope.
  const courses = await api.list(
    "/api/v1/courses",
    "?enrollment_state=active&per_page=50",
  );
  await checkIdentity();
  const available = new Set(courses.map((course) => id(course.id)));
  if (selected.some((course) => !available.has(course)))
    throw new ProbeError("course_not_accessible");
  const report = {
    schemaVersion: 1,
    evidence: "probe_output_not_acceptance",
    discoveredCourses: courses.length,
    selectedCourses: selected.length,
    courses: [],
    classification: "partial_probe",
  };
  for (const course of selected) {
    await checkIdentity();
    const result = { courseOrdinal: report.courses.length + 1, resources: {} };
    const resource = async (name, fn) => {
      try {
        result.resources[name] = { state: "read", ...(await fn()) };
      } catch (error) {
        result.resources[name] = {
          state: "incomplete",
          reason: error instanceof ProbeError ? error.code : "probe_failed",
        };
      }
      // Identity failure invalidates the entire report, even after a restricted read.
      await checkIdentity();
    };
    await resource("syllabus", async () => {
      const { data } = await api.get(
        `/api/v1/courses/${course}`,
        "?include[]=syllabus_body",
      );
      const text = data.syllabus_body;
      return {
        inlineBodyPresent: typeof text === "string" && text.trim().length > 0,
        linkedDocumentsRead: false,
        coverage: "partial",
      };
    });
    await resource("assignments", async () => {
      const assignments = await api.list(
        `/api/v1/courses/${course}/assignments`,
      );
      return {
        count: assignments.length,
        withInstructions: assignments.filter(
          (a) => typeof a.description === "string" && a.description.trim(),
        ).length,
        withRubric: assignments.filter(
          (a) => Array.isArray(a.rubric) && a.rubric.length > 0,
        ).length,
      };
    });
    await resource("discussion", async () => {
      const topics = await api.list(
        `/api/v1/courses/${course}/discussion_topics`,
      );
      if (!topics.length)
        return { count: 0, viewRead: false, coverage: "partial" };
      const topic = topics.find((t) => t.user_can_see_posts === true);
      if (!topic) throw new ProbeError("posts_restricted_or_unknown");
      const { data } = await api.get(
        `/api/v1/courses/${course}/discussion_topics/${id(topic.id)}/view`,
      );
      if (!Array.isArray(data.view))
        throw new ProbeError("invalid_discussion_view");
      return {
        count: topics.length,
        viewRead: true,
        topLevelEntries: data.view.length,
        coverage: "one_topic_sample",
      };
    });
    report.courses.push(result);
  }
  await checkIdentity();
  return report; // Counts/status only; never IDs, titles, HTML, names or provider error bodies.
}
