// Shared bounded reader and P0-M1 diagnostic. No persistence or Wrytely upload.
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

async function cancelBody(body) {
  // Cleanup must not replace a controlled failure with a provider exception.
  try {
    await body?.cancel();
  } catch {
    // The request is already being discarded.
  }
}

async function boundedText(response, maxBytes, strict = false) {
  if (Number(response.headers.get("content-length")) > maxBytes) {
    await cancelBody(response.body);
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
    await cancelBody(reader);
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder("utf-8", { fatal: strict }).decode(bytes);
}

export function nextLink(link) {
  // Consume the whole header; a valid relation must not hide trailing garbage.
  // Commas inside an opaque URL are preserved.
  const links = link
    ? link.split(/,(?=\s*<)/).map((part) => {
        const match = part.match(/^\s*<([^>]+)>\s*;\s*rel="([^"]+)"\s*$/);
        if (!match) throw new ProbeError("invalid_pagination");
        return match;
      })
    : [];
  const following = links.filter((x) => x[2].split(/\s+/).includes("next"));
  if (following.length > 1) throw new ProbeError("invalid_pagination");
  return following.length ? following[0][1] : null;
}

export function makeReader(originValue, fetchImpl = fetch, maxPages = 10) {
  const origin = checkedOrigin(originValue);
  async function get(path, query = "") {
    const url = safeURL(path + query, origin, path);
    return read(url);
  }
  async function read(url, strict = false) {
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
      await cancelBody(response.body);
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
    if (strict && (response.status !== 200 || response.url !== url)) {
      await cancelBody(response.body);
      throw new ProbeError("invalid_response");
    }
    if (
      !/^application\/json(?:;|$)/i.test(
        response.headers.get("content-type") ?? "",
      )
    ) {
      await cancelBody(response.body);
      throw new ProbeError("login_or_non_json");
    }
    let data;
    try {
      data = JSON.parse(await boundedText(response, 1024 * 1024, strict));
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
      const following = nextLink(link);
      next = following ? safeURL(following, origin, path) : null;
    }
    return items;
  }
  function courseURL(value) {
    try {
      if (
        typeof value !== "string" ||
        [...value].length > 4000 ||
        /[\u0000-\u0020\u007f\uD800-\uDFFF]/u.test(value)
      )
        throw Error();
      const url = new URL(value);
      if (safeURL(value, origin, "/api/v1/courses") !== url.href) throw Error();
      const allowed = ["enrollment_state", "per_page", "page"];
      if (
        [...url.searchParams.keys()].some((k) => !allowed.includes(k)) ||
        allowed.some((k) => url.searchParams.getAll(k).length > 1) ||
        url.searchParams.get("enrollment_state") !== "active" ||
        url.searchParams.get("per_page") !== "50" ||
        (url.searchParams.has("page") && !url.searchParams.get("page"))
      )
        throw Error();
      return url.href;
    } catch {
      throw new ProbeError("unsafe_pagination");
    }
  }
  async function coursePage(cursor = null) {
    const url = courseURL(
      cursor === null
        ? `${origin}/api/v1/courses?enrollment_state=active&per_page=50`
        : cursor,
    );
    const { data, link } = await read(url, true);
    if (
      !Array.isArray(data) ||
      data.length > 50 ||
      data.some(
        (row) => row === null || typeof row !== "object" || Array.isArray(row),
      )
    )
      throw new ProbeError("invalid_collection");
    if (new TextEncoder().encode(link).length > 16384)
      throw new ProbeError("invalid_pagination");
    const following = nextLink(link);
    const next_cursor = following === null ? null : courseURL(following);
    if (next_cursor === url) throw new ProbeError("pagination_cycle");
    return { data, next_cursor };
  }
  async function assignmentPage(course, cursor = null) {
    if (typeof course !== "string" || !/^[1-9][0-9]{0,19}$/.test(course))
      throw new ProbeError("invalid_provider_id");
    const path = `/api/v1/courses/${course}/assignments`;
    function checked(value) {
      try {
        if (
          typeof value !== "string" ||
          [...value].length > 4000 ||
          /[\u0000-\u0020\u007f\uD800-\uDFFF]/u.test(value)
        )
          throw Error();
        const url = new URL(value);
        if (safeURL(value, origin, path) !== url.href) throw Error();
        const allowed = ["per_page", "override_assignment_dates", "page"];
        if (
          [...url.searchParams.keys()].some((k) => !allowed.includes(k)) ||
          allowed.some((k) => url.searchParams.getAll(k).length > 1) ||
          url.searchParams.get("per_page") !== "50" ||
          url.searchParams.get("override_assignment_dates") !== "true" ||
          (url.searchParams.has("page") && !url.searchParams.get("page"))
        )
          throw Error();
        return url.href;
      } catch {
        throw new ProbeError("unsafe_pagination");
      }
    }
    const url = checked(
      cursor ?? `${origin}${path}?per_page=50&override_assignment_dates=true`,
    );
    const { data, link } = await read(url, true);
    const ids = new Set();
    if (
      !Array.isArray(data) ||
      data.length > 50 ||
      data.some((row) => {
        if (!row || typeof row !== "object" || Array.isArray(row)) return true;
        for (const value of [row.id, row.course_id])
          if (
            !["string", "number"].includes(typeof value) ||
            (typeof value === "number" && !Number.isSafeInteger(value)) ||
            !/^[1-9][0-9]{0,19}$/.test(String(value))
          )
            return true;
        if (String(row.course_id) !== course || ids.has(String(row.id)))
          return true;
        ids.add(String(row.id));
        return false;
      })
    )
      throw new ProbeError("invalid_collection");
    if (new TextEncoder().encode(link).length > 16384)
      throw new ProbeError("invalid_pagination");
    const following = nextLink(link),
      next_cursor = following === null ? null : checked(following);
    if (next_cursor === url) throw new ProbeError("pagination_cycle");
    return { data, next_cursor };
  }
  async function getStrict(path, query = "") {
    return read(safeURL(path + query, origin, path), true);
  }
  return { get, getStrict, list, coursePage, assignmentPage };
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
