// Selected-course reads only. No cookies exported, writes, extraction or storage.
import {
  makeReader,
  checkedOrigin,
  ProbeError,
  nextLink,
} from "../canvas-feasibility/probe.mjs";
const identifier = (x) => {
  if (
    !["string", "number"].includes(typeof x) ||
    (typeof x === "number" && !Number.isSafeInteger(x)) ||
    !/^[1-9][0-9]{0,19}$/.test(String(x))
  )
    throw new ProbeError("invalid_provider_id");
  return String(x);
};
const row = (x) => x && typeof x === "object" && !Array.isArray(x);
export function makeDocumentReader(originValue, fetchImpl = fetch) {
  const origin = checkedOrigin(originValue),
    api = makeReader(origin, fetchImpl);
  return async function documentPage(course, kind, cursor, expectedSubject) {
    course = identifier(course);
    if (!["assignments", "syllabus", "pages"].includes(kind))
      throw new ProbeError("invalid_collection");
    async function identity() {
      const current = (await api.getStrict("/api/v1/users/self/profile")).data
        .id;
      if (identifier(current) !== expectedSubject)
        throw new ProbeError("canvas_account_changed");
    }
    async function get(path, query = "") {
      await identity();
      const response = await api.getStrict(path, query);
      await identity();
      return response;
    }
    const base = `/api/v1/courses/${course}`;
    if (kind === "syllabus") {
      if (cursor !== null) throw new ProbeError("unsafe_pagination");
      const { data } = await get(base, "?include[]=syllabus_body");
      if (!row(data) || identifier(data.id) !== course)
        throw new ProbeError("invalid_collection");
      return { data: [data], next_cursor: null };
    }
    const path = `${base}/${kind}`;
    const initial = `${origin}${path}?per_page=4${kind === "assignments" ? "&override_assignment_dates=true" : ""}`;
    function checked(value) {
      try {
        if (
          typeof value !== "string" ||
          value.length > 4000 ||
          /[\u0000-\u0020\u007f]/u.test(value)
        )
          throw Error();
        const url = new URL(value);
        const allowed = [
          "per_page",
          "page",
          ...(kind === "assignments" ? ["override_assignment_dates"] : []),
        ];
        if (
          url.origin !== origin ||
          url.pathname !== path ||
          url.username ||
          url.password ||
          url.hash ||
          [...url.searchParams.keys()].some((k) => !allowed.includes(k)) ||
          allowed.some((k) => url.searchParams.getAll(k).length > 1) ||
          url.searchParams.get("per_page") !== "4" ||
          (kind === "assignments" &&
            url.searchParams.get("override_assignment_dates") !== "true") ||
          (url.searchParams.has("page") && !url.searchParams.get("page"))
        )
          throw Error();
        return url;
      } catch {
        throw new ProbeError("unsafe_pagination");
      }
    }
    const url = checked(cursor ?? initial);
    const { data, link } = await get(path, url.search);
    if (
      !Array.isArray(data) ||
      data.length > 4 ||
      new TextEncoder().encode(link).length > 16384
    )
      throw new ProbeError("invalid_collection");
    const seen = new Set(),
      details = [];
    for (const item of data) {
      if (!row(item)) throw new ProbeError("invalid_collection");
      const id = identifier(kind === "assignments" ? item.id : item.page_id);
      if (seen.has(id)) throw new ProbeError("invalid_collection");
      seen.add(id);
      if (kind === "assignments" && identifier(item.course_id) !== course)
        throw new ProbeError("invalid_collection");
      // List rows may omit rubric/body. Read each authoritative detail, never guess.
      const detail = (
        await get(
          `${path}/${id}`,
          kind === "assignments" ? "?override_assignment_dates=true" : "",
        )
      ).data;
      if (
        !row(detail) ||
        identifier(kind === "assignments" ? detail.id : detail.page_id) !==
          id ||
        (kind === "assignments" && identifier(detail.course_id) !== course)
      )
        throw new ProbeError("invalid_collection");
      details.push(detail);
    }
    const following = nextLink(link);
    const next_cursor = following === null ? null : checked(following).href;
    if (next_cursor === url.href) throw new ProbeError("pagination_cycle");
    return { data: details, next_cursor };
  };
}
