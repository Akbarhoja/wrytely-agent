import { ProbeError, nextLink } from "../canvas-feasibility/probe.mjs";
const prefix = "wrytely-modules-v1:";
const id = (x) => {
  if (
    !["string", "number"].includes(typeof x) ||
    (typeof x === "number" && !Number.isSafeInteger(x)) ||
    !/^[1-9][0-9]{0,19}$/.test(String(x))
  )
    throw new ProbeError("invalid_collection");
  return String(x);
};
function checked(value, origin, path) {
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
        (x) => !["per_page", "page"].includes(x),
      ) ||
      ["per_page", "page"].some((x) => u.searchParams.getAll(x).length > 1) ||
      u.searchParams.get("per_page") !== "4" ||
      (u.searchParams.has("page") && !u.searchParams.get("page"))
    )
      throw Error();
    return u;
  } catch {
    throw new ProbeError("unsafe_pagination");
  }
}
export async function readModulePage({ course, cursor, origin, get }) {
  const base = `/api/v1/courses/${course}/modules`;
  let state = null;
  if (typeof cursor === "string" && cursor.startsWith(prefix)) {
    try {
      if (cursor.length > 4000) throw Error();
      state = JSON.parse(cursor.slice(prefix.length));
      if (
        Object.keys(state).sort().join() !==
          "course,item_next,module_next,modules,version" ||
        state.version !== 1 ||
        state.course !== course ||
        !Array.isArray(state.modules) ||
        !state.modules.length ||
        state.modules.length > 4 ||
        state.modules.some((x) => id(x) !== x) ||
        new Set(state.modules).size !== state.modules.length ||
        prefix + JSON.stringify(state) !== cursor
      )
        throw Error();
      if (state.module_next !== null) checked(state.module_next, origin, base);
      if (state.item_next !== null)
        checked(state.item_next, origin, `${base}/${state.modules[0]}/items`);
    } catch {
      throw new ProbeError("unsafe_pagination");
    }
  }
  const path = state ? `${base}/${state.modules[0]}/items` : base;
  const url = checked(
    (state ? state.item_next : cursor) ?? `${origin}${path}?per_page=4`,
    origin,
    path,
  );
  const { data, link } = await get(path, url.search);
  if (
    !Array.isArray(data) ||
    data.length > 4 ||
    new TextEncoder().encode(link).length > 16384
  )
    throw new ProbeError("invalid_collection");
  const ids = new Set();
  for (const item of data) {
    if (
      !item ||
      typeof item !== "object" ||
      Array.isArray(item) ||
      ids.has(id(item.id))
    )
      throw new ProbeError("invalid_collection");
    ids.add(id(item.id));
    if (
      state &&
      item.module_id != null &&
      id(item.module_id) !== state.modules[0]
    )
      throw new ProbeError("invalid_collection");
  }
  const next = nextLink(link),
    following = next === null ? null : checked(next, origin, path).href;
  if (following === url.href) throw new ProbeError("pagination_cycle");
  const result = data.map((x) => ({
    ...x,
    _wrytely_module: state ? state.modules[0] : null,
  }));
  if (state) {
    state.item_next = following;
    if (following === null) state.modules.shift();
  } else
    state = {
      version: 1,
      course,
      modules: [...ids],
      module_next: following,
      item_next: null,
    };
  const continuation = state.modules.length
    ? prefix + JSON.stringify(state)
    : state.module_next;
  if (continuation?.length > 4000) throw new ProbeError("size_limit");
  return { data: result, next_cursor: continuation };
}

export function prepareModuleDocuments({ resource_key, page, origin }) {
  const [course] = resource_key.split("/");
  const nullable = (x) => (x == null ? null : String(x));
  const documents = page.data.map((raw) => {
    const item = raw._wrytely_module !== null,
      provider_id = id(raw.id);
    const fields = item
      ? {
          module_id: id(raw._wrytely_module),
          position: nullable(raw.position),
          type: nullable(raw.type),
          content_id: raw.content_id == null ? null : id(raw.content_id),
          page_url: nullable(raw.page_url),
          completion_requirement:
            raw.completion_requirement == null
              ? null
              : JSON.stringify(raw.completion_requirement),
        }
      : {
          position: nullable(raw.position),
          unlock_at: nullable(raw.unlock_at),
          require_sequential_progress: raw.require_sequential_progress ?? null,
          prerequisite_module_ids:
            raw.prerequisite_module_ids == null
              ? null
              : raw.prerequisite_module_ids.map(id).sort(),
          state: nullable(raw.state),
        };
    const title = raw.title ?? raw.name;
    if (
      typeof title !== "string" ||
      !title.trim() ||
      [...title.normalize("NFC")].length > 300
    )
      throw new ProbeError("invalid_collection");
    return {
      owner_object: { kind: item ? "module_item" : "module", provider_id },
      object_fields: fields,
      metadata: {
        title,
        format: "text",
        extractor_version: "canvas.json.v1",
        provider_updated_at: raw.updated_at ?? null,
        coverage: "partial",
        missing: [
          item ? "module_item_content_separate" : "module_items_separate",
        ],
      },
      source: { text: JSON.stringify(fields, null, 2) },
      reference: `${origin}/courses/${course}/modules/${item ? fields.module_id : provider_id}`,
    };
  });
  return {
    resource_key,
    observed_at: new Date().toISOString(),
    documents,
    next_cursor: page.next_cursor,
    coverage: {
      state: page.next_cursor ? "partial" : "complete",
      reason: page.next_cursor ? "more_pages" : null,
    },
  };
}
