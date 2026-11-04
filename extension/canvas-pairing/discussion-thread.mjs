// Content-free continuation state in the existing scan cursor, not a second journal.
import { ProbeError, nextLink } from "../canvas-feasibility/probe.mjs";
const prefix = "wrytely-discussion-v1:";
const id = (x) => {
  if (
    !["number", "string"].includes(typeof x) ||
    (typeof x === "number" && !Number.isSafeInteger(x)) ||
    !/^[1-9][0-9]{0,19}$/.test(String(x))
  )
    throw new ProbeError("invalid_collection");
  return String(x);
};
const exact = (x, keys) =>
  x &&
  typeof x === "object" &&
  !Array.isArray(x) &&
  Object.keys(x).length === keys.length &&
  keys.every((k) => Object.hasOwn(x, k));
function pageURL(value, origin, path, size) {
  try {
    if (
      typeof value !== "string" ||
      value.length > 4000 ||
      /[\u0000-\u0020\u007f]/u.test(value)
    )
      throw Error();
    const url = new URL(value),
      keys = ["per_page", "page"];
    if (
      url.origin !== origin ||
      url.pathname !== path ||
      url.username ||
      url.password ||
      url.hash ||
      [...url.searchParams.keys()].some((k) => !keys.includes(k)) ||
      keys.some((k) => url.searchParams.getAll(k).length > 1) ||
      url.searchParams.get("per_page") !== String(size) ||
      (url.searchParams.has("page") && !url.searchParams.get("page"))
    )
      throw Error();
    return url;
  } catch {
    throw new ProbeError("unsafe_pagination");
  }
}
function validate(s, course, origin) {
  if (
    !exact(s, [
      "version",
      "course",
      "topics",
      "topic_next",
      "phase",
      "entries_next",
      "parents",
      "replies_next",
    ]) ||
    s.version !== 1 ||
    s.course !== course ||
    !Array.isArray(s.topics) ||
    s.topics.length < 1 ||
    s.topics.length > 4 ||
    s.topics.some((x) => id(x) !== x) ||
    new Set(s.topics).size !== s.topics.length ||
    !["entries", "replies"].includes(s.phase) ||
    !Array.isArray(s.parents) ||
    s.parents.length > 4 ||
    s.parents.some((x) => id(x) !== x) ||
    new Set(s.parents).size !== s.parents.length ||
    (s.phase === "entries"
      ? s.parents.length || s.replies_next !== null
      : !s.parents.length)
  )
    throw new ProbeError("unsafe_pagination");
  const base = `/api/v1/courses/${course}/discussion_topics`;
  if (s.topic_next !== null) pageURL(s.topic_next, origin, base, 4);
  if (s.entries_next !== null)
    pageURL(s.entries_next, origin, `${base}/${s.topics[0]}/entries`, 4);
  if (s.replies_next !== null)
    pageURL(
      s.replies_next,
      origin,
      `${base}/${s.topics[0]}/entries/${s.parents[0]}/replies`,
      4,
    );
}
function encode(s, course, origin) {
  if (!s.topics.length) return s.topic_next;
  validate(s, course, origin);
  const cursor = prefix + JSON.stringify(s);
  if (cursor.length > 4000) throw new ProbeError("size_limit");
  return cursor;
}
export function discussionContinuation(course, details, topic_next, origin) {
  const topics = details
    .filter((x) => x.user_can_see_posts === true && x.locked_for_user !== true)
    .map((x) => id(x.id));
  return encode(
    {
      version: 1,
      course,
      topics,
      topic_next,
      phase: "entries",
      entries_next: null,
      parents: [],
      replies_next: null,
    },
    course,
    origin,
  );
}
export const isDiscussionCursor = (cursor) =>
  typeof cursor === "string" && cursor.startsWith(prefix);
export async function readDiscussionThread({ course, cursor, origin, get }) {
  let s;
  try {
    if (cursor.length > 4000) throw Error();
    s = JSON.parse(cursor.slice(prefix.length));
    validate(s, course, origin);
    if (prefix + JSON.stringify(s) !== cursor) throw Error();
  } catch {
    throw new ProbeError("unsafe_pagination");
  }
  const base = `/api/v1/courses/${course}/discussion_topics/${s.topics[0]}`;
  // Visibility can change between worker runs. Recheck the topic before each page.
  const topic = (await get(base)).data;
  if (!topic || id(topic.id) !== s.topics[0] || topic.is_announcement !== false)
    throw new ProbeError("invalid_collection");
  const advance = () => {
    s.topics.shift();
    s.phase = "entries";
    s.entries_next = null;
    s.parents = [];
    s.replies_next = null;
  };
  if (topic.user_can_see_posts !== true || topic.locked_for_user === true) {
    advance();
    return { data: [], next_cursor: encode(s, course, origin) };
  }
  const parent = s.phase === "replies" ? s.parents[0] : null;
  const path = parent ? `${base}/entries/${parent}/replies` : `${base}/entries`;
  const url = pageURL(
    (parent ? s.replies_next : s.entries_next) ?? `${origin}${path}?per_page=4`,
    origin,
    path,
    4,
  );
  const { data, link } = await get(path, url.search);
  if (
    !Array.isArray(data) ||
    data.length > 4 ||
    new TextEncoder().encode(link).length > 16384
  )
    throw new ProbeError("invalid_collection");
  const seen = new Set();
  const entries = data.map((raw) => {
    if (!raw || typeof raw !== "object" || Array.isArray(raw))
      throw new ProbeError("invalid_collection");
    const entry = id(raw.id);
    if (
      seen.has(entry) ||
      (raw.parent_id != null && id(raw.parent_id) !== parent)
    )
      throw new ProbeError("invalid_collection");
    seen.add(entry);
    // Overwrite derived context; provider payload cannot forge topic/parent binding.
    return {
      ...raw,
      _wrytely_entry: {
        topic_id: id(topic.id),
        parent_entry_id: parent,
        required_initial_post:
          typeof topic.require_initial_post === "boolean"
            ? topic.require_initial_post
            : null,
      },
    };
  });
  const following = nextLink(link),
    next = following === null ? null : pageURL(following, origin, path, 4).href;
  if (next === url.href) throw new ProbeError("pagination_cycle");
  if (parent) {
    s.replies_next = next;
    if (next === null) {
      s.parents.shift();
      if (!s.parents.length) {
        s.phase = "entries";
        if (s.entries_next === null) advance();
      }
    }
  } else {
    s.entries_next = next;
    s.parents = [...seen];
    if (s.parents.length) s.phase = "replies";
    else if (next === null) advance();
  }
  return { data: entries, next_cursor: encode(s, course, origin) };
}
