// Course-scoped link discovery after denied file enumeration. No independent cache.
import { ProbeError, nextLink } from "../canvas-feasibility/probe.mjs";
import { readFileObjects } from "./file-documents.mjs";

export const LINKED_FILES_CURSOR = "wrytely-linked-files-v1:";
const numeric = (v) => typeof v === "string" && /^[1-9][0-9]{0,19}$/.test(v);
const fail = (code = "unsafe_pagination") => {
  throw new ProbeError(code);
};

// Require an explicitly recognized ordinary assignment shape. Missing/malformed
// types or quiz markers are not evidence that this is a non-quiz assignment.
export function ordinaryLinkedAssignment(row) {
  if (row.locked_for_user !== false || row.quiz_id != null) return false;
  for (const key of ["is_quiz_assignment", "is_quiz_lti_assignment"]) {
    if (Object.hasOwn(row, key) && row[key] !== false) return false;
  }
  const allowed = new Set([
    "online_upload",
    "online_text_entry",
    "online_url",
    "media_recording",
    "on_paper",
    "none",
    "not_graded",
  ]);
  return (
    Array.isArray(row.submission_types) &&
    row.submission_types.length > 0 &&
    row.submission_types.every((t) => allowed.has(t))
  );
}

// Deliberately a narrow recognizer, not an HTML renderer or completeness claim.
// Ignore script/comment/embedded regions; accept quoted hrefs on actual anchors.
export function linkedFileIds(html, origin, course) {
  if (typeof html !== "string" || html.length > 1048576) fail("size_limit");
  const clean = html.replace(
    /<!--[\s\S]*?(?:-->|$)|<(script|style|template|iframe|object)\b[^>]*>[\s\S]*?(?:<\/\1\s*>|$)/gi,
    "",
  );
  const ids = new Set();
  for (const match of clean.matchAll(/<a\b((?:[^>"']|"[^"]*"|'[^']*')*)>/gi)) {
    const attrs = [
      ...match[1].matchAll(
        /([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g,
      ),
    ].filter((a) => a[1].toLowerCase() === "href");
    if (
      attrs.length !== 1 ||
      (attrs[0][2] === undefined && attrs[0][3] === undefined)
    )
      continue;
    let value = (attrs[0][2] ?? attrs[0][3]).replace(/&amp;/g, "&");
    if (/[&](?:#|[a-z])/i.test(value) || /[\u0000-\u0020\u007f\\]/u.test(value))
      continue;
    try {
      if (
        value
          .split(/[?#]/)[0]
          .split("/")
          .some((p) => [".", ".."].includes(decodeURIComponent(p)))
      )
        continue;
      const u = new URL(value, origin);
      const file = new RegExp(
        `^/(?:api/v1/)?courses/${course}/files/([1-9][0-9]{0,19})(?:/download)?$`,
      ).exec(u.pathname);
      if (
        u.origin !== origin ||
        u.username ||
        u.password ||
        u.hash ||
        !file ||
        [...u.searchParams.keys()].some(
          (k) => !["wrap", "download_frd"].includes(k),
        ) ||
        ["wrap", "download_frd"].some(
          (k) =>
            u.searchParams.has(k) &&
            (u.searchParams.getAll(k).length !== 1 ||
              u.searchParams.get(k) !== "1"),
        )
      )
        continue;
      ids.add(file[1]);
      if (ids.size > 64) fail("size_limit");
    } catch (e) {
      if (e?.code) throw e;
    }
  }
  return [...ids].sort();
}

function checkedPage(value, origin, course) {
  const path = `/api/v1/courses/${course}/assignments`;
  if (typeof value !== "string" || value.length > 2000) fail();
  const u = new URL(value);
  if (
    u.origin !== origin ||
    u.pathname !== path ||
    u.username ||
    u.password ||
    u.hash ||
    [...u.searchParams.keys()].some((k) => !["per_page", "page"].includes(k)) ||
    u.searchParams.get("per_page") !== "4" ||
    ["per_page", "page"].some((k) => u.searchParams.getAll(k).length > 1) ||
    (u.searchParams.has("page") &&
      !/^[1-9][0-9]{0,3}$/.test(u.searchParams.get("page")))
  )
    fail();
  return u;
}

function encode(state) {
  const cursor = LINKED_FILES_CURSOR + JSON.stringify(state);
  if (cursor.length > 4000) fail("size_limit");
  return cursor;
}

export async function readLinkedFilePage({
  course,
  cursor,
  origin,
  get,
  transport,
  identity,
  selectedKinds,
}) {
  const parents = ["syllabus", "assignments"].filter((k) =>
    selectedKinds.includes(k),
  );
  if (!selectedKinds.includes("files") || !parents.length)
    fail("permission_denied");
  let s;
  if (cursor === null)
    s = {
      v: 1,
      course,
      parents,
      stage: parents[0],
      next: null,
      pages: 0,
      links: [],
      offset: 0,
    };
  else {
    try {
      if (
        typeof cursor !== "string" ||
        cursor.length > 4000 ||
        !cursor.startsWith(LINKED_FILES_CURSOR)
      )
        fail();
      s = JSON.parse(cursor.slice(LINKED_FILES_CURSOR.length));
      if (
        Object.keys(s).sort().join() !==
          "course,links,next,offset,pages,parents,stage,v" ||
        s.v !== 1 ||
        s.course !== course ||
        JSON.stringify(s.parents) !== JSON.stringify(parents) ||
        ![...parents, "files"].includes(s.stage) ||
        !Number.isSafeInteger(s.pages) ||
        s.pages < 0 ||
        s.pages > 100 ||
        !Array.isArray(s.links) ||
        s.links.length > 64 ||
        !Number.isSafeInteger(s.offset) ||
        s.offset < 0 ||
        s.offset > s.links.length ||
        (s.stage !== "files" && s.offset !== 0) ||
        s.links.some(
          (x) =>
            !Array.isArray(x) ||
            x.length !== 2 ||
            !numeric(x[0]) ||
            !Array.isArray(x[1]) ||
            !x[1].length ||
            x[1].length > 32 ||
            x[1].some(
              (p) =>
                typeof p !== "string" ||
                !/^(assignment|syllabus):[1-9][0-9]{0,19}$/.test(p) ||
                (p.startsWith("syllabus:")
                  ? !parents.includes("syllabus") || p !== `syllabus:${course}`
                  : !parents.includes("assignments")),
            ) ||
            new Set(x[1]).size !== x[1].length ||
            JSON.stringify(x[1]) !== JSON.stringify([...x[1]].sort()),
        ) ||
        new Set(s.links.map((x) => x[0])).size !== s.links.length ||
        (s.next !== null &&
          (s.stage !== "assignments" ||
            !checkedPage(s.next, origin, course))) ||
        encode(s) !== cursor
      )
        fail();
    } catch {
      fail();
    }
  }
  const finish = (data = []) => ({
    data,
    next_cursor:
      s.stage === "files" && s.offset === s.links.length ? null : encode(s),
    coverage: { state: "partial", reason: "permission_denied" },
  });
  if (s.stage === "files") {
    const data = [];
    for (const [file, from] of s.links.slice(s.offset, s.offset + 4)) {
      try {
        const rows = await readFileObjects({
          course,
          items: [{ id: file }],
          origin,
          get,
          transport,
          identity,
        });
        data.push({ ...rows[0], _wrytely_linked_from: from });
      } catch (e) {
        if (!["permission_denied", "not_found"].includes(e?.code)) throw e;
      }
      s.offset++;
    }
    return finish(data);
  }
  function add(html, parent) {
    for (const file of linkedFileIds(html ?? "", origin, course)) {
      let link = s.links.find((x) => x[0] === file);
      if (!link) {
        link = [file, []];
        s.links.push(link);
      }
      if (!link[1].includes(parent)) link[1].push(parent);
      link[1].sort();
      if (s.links.length > 64 || link[1].length > 32) fail("size_limit");
    }
  }
  let more = null;
  try {
    if (s.stage === "syllabus") {
      const raw = (
        await get(`/api/v1/courses/${course}`, "?include[]=syllabus_body")
      ).data;
      if (String(raw?.id) !== course) fail("invalid_collection");
      if (raw.locked_for_user !== true)
        add(raw.syllabus_body, `syllabus:${course}`);
    } else {
      if (++s.pages > 100) fail("size_limit");
      const u = checkedPage(
        s.next ?? `${origin}/api/v1/courses/${course}/assignments?per_page=4`,
        origin,
        course,
      );
      const { data, link } = await get(u.pathname, u.search);
      if (
        !Array.isArray(data) ||
        data.length > 4 ||
        typeof link !== "string" ||
        link.length > 16384
      )
        fail("invalid_collection");
      const seen = new Set();
      for (const row of data) {
        const id = String(row?.id);
        if (!numeric(id) || String(row.course_id) !== course || seen.has(id))
          fail("invalid_collection");
        seen.add(id);
        if (ordinaryLinkedAssignment(row))
          add(row.description, `assignment:${id}`);
      }
      const next = nextLink(link);
      more = next === null ? null : checkedPage(next, origin, course).href;
      if (more === u.href) fail("pagination_cycle");
    }
  } catch (e) {
    if (!["permission_denied", "not_found"].includes(e?.code)) throw e;
  }
  if (more) s.next = more;
  else {
    s.stage = parents[parents.indexOf(s.stage) + 1] ?? "files";
    s.next = null;
  }
  return finish();
}
