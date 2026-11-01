// Worker-side C1 transport and bounded metadata collector. No scheduler or token export.
import { checkedOrigin, makeReader } from "../canvas-feasibility/probe.mjs";
import { discoveryOperations, discoveryConflicts } from "./discovery.mjs";

const active = new WeakSet();
const quarantined = new WeakMap();
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const secret = /^[A-Za-z0-9_-]{43}$/;
const expiry =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(?:Z|[+-](\d{2}):(\d{2}))$/;

export class PairingClientError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

const fail = (code) => {
  throw new PairingClientError(code);
};

function origin(value) {
  try {
    if (
      typeof value !== "string" ||
      checkedOrigin(value) !== value ||
      !/^https:\/\/[a-z0-9]+(?:[.-][a-z0-9]+)*$/.test(value)
    )
      throw Error();
    return value;
  } catch {
    fail("invalid_configuration");
  }
}

function validExpiry(value) {
  if (typeof value !== "string") return false;
  const match = expiry.exec(value);
  if (!match) return false;
  const [
    year,
    month,
    day,
    hour,
    minute,
    second,
    offsetHour = 0,
    offsetMinute = 0,
  ] = match.slice(1).map((x) => (x === undefined ? 0 : Number(x)));
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return (
    year >= 1 &&
    month >= 1 &&
    month <= 12 &&
    day >= 1 &&
    day <= days[month - 1] &&
    hour <= 23 &&
    minute <= 59 &&
    second <= 59 &&
    offsetHour <= 23 &&
    offsetMinute <= 59 &&
    Number.isFinite(Date.parse(value))
  );
}

function projection(value, canvasOrigin, states) {
  if (
    !value ||
    typeof value !== "object" ||
    typeof value.connection_id !== "string" ||
    !uuid.test(value.connection_id) ||
    value.provider !== "canvas_extension" ||
    value.origin !== canvasOrigin ||
    !states.includes(value.state) ||
    !Number.isSafeInteger(value.generation) ||
    value.generation < 1 ||
    !validExpiry(value.credential_expires_at)
  ) {
    throw Error();
  }
  return Object.fromEntries(
    [
      "connection_id",
      "provider",
      "origin",
      "state",
      "generation",
      "credential_expires_at",
    ].map((key) => [key, value[key]]),
  );
}

function contextProjection(value, canvasOrigin) {
  const connection = projection(value, canvasOrigin, [
    "pending_identity",
    "connected",
    "reconnect_required",
  ]);
  const kinds = [
    "syllabus",
    "assignments",
    "announcements",
    "discussions",
    "modules",
    "pages",
    "files",
    "submissions",
    "grades",
  ];
  if (
    !Number.isSafeInteger(value.scope_revision) ||
    value.scope_revision < 0 ||
    !["explicit_set", "all_active"].includes(value.mode) ||
    !Array.isArray(value.course_ids) ||
    value.course_ids.length > 1000 ||
    value.course_ids.some(
      (id) => typeof id !== "string" || !/^[1-9][0-9]{0,19}$/.test(id),
    ) ||
    new Set(value.course_ids).size !== value.course_ids.length ||
    !Array.isArray(value.resource_kinds) ||
    value.resource_kinds.length > kinds.length ||
    value.resource_kinds.some((kind) => !kinds.includes(kind)) ||
    new Set(value.resource_kinds).size !== value.resource_kinds.length ||
    !value.discovery ||
    typeof value.discovery !== "object" ||
    !["unknown", "complete", "partial", "restricted", "unsupported"].includes(
      value.discovery.coverage,
    ) ||
    ["last_attempt_at", "last_complete_at"].some(
      (key) =>
        value.discovery[key] !== null && !validExpiry(value.discovery[key]),
    )
  )
    throw Error();
  return {
    ...connection,
    scope_revision: value.scope_revision,
    mode: value.mode,
    course_ids: [...value.course_ids],
    resource_kinds: [...value.resource_kinds],
    discovery: Object.fromEntries(
      ["coverage", "last_attempt_at", "last_complete_at"].map((key) => [
        key,
        value.discovery[key],
      ]),
    ),
  };
}

async function cancel(body) {
  try {
    await body?.cancel();
  } catch {
    /* Cleanup must not echo/mask the primary failure. */
  }
}

async function jsonBody(response, limit = 16384) {
  if (
    !/^application\/json(?:;|$)/i.test(
      response.headers.get("content-type") ?? "",
    )
  ) {
    await cancel(response.body);
    throw Error();
  }
  const reader = response.body?.getReader();
  if (!reader) throw Error();
  const chunks = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > limit) throw Error();
      chunks.push(value);
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      /* Controlled outer error only. */
    }
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
}

export function createPairingClient({
  apiOrigin: apiInput,
  canvasOrigin: canvasInput,
  storageArea,
  fetchImpl = fetch,
  canvasFetch = fetch,
} = {}) {
  const apiOrigin = origin(apiInput),
    canvasOrigin = origin(canvasInput);
  if (
    !storageArea ||
    ["setAccessLevel", "get", "set", "remove"].some(
      (name) => typeof storageArea[name] !== "function",
    )
  ) {
    fail("storage_unavailable");
  }
  const key = `wrytely.canvas.connection.v1:${apiOrigin}:${canvasOrigin}`;
  const suspect = () => quarantined.get(storageArea)?.has(key);
  function mark(value) {
    if (!quarantined.has(storageArea)) quarantined.set(storageArea, new Set());
    if (value) quarantined.get(storageArea).add(key);
    else quarantined.get(storageArea).delete(key);
  }
  async function secure() {
    try {
      await storageArea.setAccessLevel({ accessLevel: "TRUSTED_CONTEXTS" });
    } catch {
      fail("storage_unavailable");
    }
  }
  async function clear() {
    mark(true);
    await storageArea.remove(key);
    mark(false);
  }
  async function cleanup(reason) {
    try {
      await clear();
    } catch {
      /* Quarantined within this worker realm. */
    }
    fail(reason);
  }
  async function run(work) {
    if (active.has(storageArea)) fail("operation_in_progress");
    active.add(storageArea);
    try {
      await secure();
      return await work();
    } finally {
      active.delete(storageArea);
    }
  }
  async function record() {
    if (suspect()) fail("storage_cleanup_required");
    let item;
    try {
      item = (await storageArea.get(key))[key];
    } catch {
      fail("storage_unavailable");
    }
    if (item === undefined) return null;
    try {
      if (
        item.schema_version !== 1 ||
        item.api_origin !== apiOrigin ||
        typeof item.ingestion_bearer !== "string" ||
        !secret.test(item.ingestion_bearer)
      )
        throw Error();
      const connection = projection(item.connection, canvasOrigin, [
        "pending_identity",
        "connected",
      ]);
      return {
        schema_version: 1,
        api_origin: apiOrigin,
        connection,
        ingestion_bearer: item.ingestion_bearer,
        ...(item.discovery === undefined ? {} : { discovery: item.discovery }),
      };
    } catch {
      return cleanup("reconnect_required");
    }
  }
  async function post(action, body, bearer) {
    const discovery =
      action.startsWith("discovery/") || action.startsWith("academic/");
    const uncertain =
      action === "redeem"
        ? "pairing_outcome_unknown"
        : discovery
          ? "discovery_outcome_unknown"
          : action === "context"
            ? "context_unavailable"
            : "binding_outcome_unknown";
    const url = `${apiOrigin}/v1/source-connections/canvas/${action}`;
    let response;
    try {
      response = await fetchImpl(url, {
        method: "POST",
        credentials: "omit",
        redirect: "error",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}),
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(15000),
      });
      if (response.url !== url || response.redirected) throw Error();
      if (!response.ok) {
        if (discovery && response.status === 409) {
          const code = (await jsonBody(response))?.detail?.code;
          fail(
            discoveryConflicts.includes(code)
              ? `discovery_${code}`
              : "discovery_state_changed",
          );
        }
        await cancel(response.body);
        if (action === "redeem" && response.status === 400)
          fail("invalid_pairing");
        if (
          (discovery || ["bind", "context"].includes(action)) &&
          response.status === 401
        )
          fail("reconnect_required");
        if (discovery && response.status === 422)
          fail("discovery_request_rejected");
        if (discovery) fail(uncertain);
        if (response.status === 429) fail("pairing_rate_limited");
        fail(uncertain);
      }
      return await jsonBody(
        response,
        action === "discovery/finish"
          ? 8 * 1024 * 1024
          : discovery
            ? 2 * 1024 * 1024
            : action === "context"
              ? 65536
              : 16384,
      );
    } catch (error) {
      if (error instanceof PairingClientError) throw error;
      await cancel(response?.body);
      fail(uncertain);
    }
  }
  const canvas = makeReader(canvasOrigin, canvasFetch);
  async function subject() {
    const value = (await canvas.get("/api/v1/users/self/profile")).data.id;
    if (
      (typeof value === "number" && !Number.isSafeInteger(value)) ||
      !["string", "number"].includes(typeof value) ||
      !/^[1-9][0-9]{0,127}$/.test(String(value))
    )
      throw Error();
    return String(value);
  }
  async function currentContext(item) {
    item ??= await record();
    if (
      !item ||
      Date.parse(item.connection.credential_expires_at) <= Date.now()
    )
      return cleanup("reconnect_required");
    let context;
    try {
      context = contextProjection(
        await post("context", { origin: canvasOrigin }, item.ingestion_bearer),
        canvasOrigin,
      );
      if (
        context.connection_id !== item.connection.connection_id ||
        context.generation < item.connection.generation
      )
        throw Error();
    } catch (error) {
      if (
        error instanceof PairingClientError &&
        error.code === "reconnect_required"
      )
        return cleanup("reconnect_required");
      fail("context_unavailable");
    }
    if (
      context.state === "reconnect_required" ||
      Date.parse(context.credential_expires_at) <= Date.now()
    )
      return cleanup("reconnect_required");
    try {
      await storageArea.set({
        [key]: {
          ...item,
          connection: projection(context, canvasOrigin, [
            "pending_identity",
            "connected",
          ]),
        },
      });
    } catch {
      fail("storage_unavailable");
    }
    if (Date.parse(context.credential_expires_at) <= Date.now())
      return cleanup("reconnect_required");
    return context;
  }
  return Object.freeze({
    ...discoveryOperations({
      run,
      record,
      currentContext,
      subject,
      fail,
      cleanup,
      canvasOrigin,
      validExpiry,
      readCoursePage: (cursor) => canvas.coursePage(cursor),
      call: (operation, body, item) =>
        post(
          operation.startsWith("academic_")
            ? `academic/${operation.slice(9)}`
            : `discovery/${operation}`,
          body,
          item.ingestion_bearer,
        ),
      invalidateAccount: async (item, value) => {
        try {
          await post(
            "bind",
            { origin: canvasOrigin, provider_subject: value },
            item.ingestion_bearer,
          );
        } catch {
          /* Local cleanup is required even if server fencing outcome is unknown. */
        }
        return cleanup("canvas_account_changed");
      },
      save: async (item, journal) => {
        try {
          await storageArea.set({ [key]: { ...item, discovery: journal } });
        } catch {
          fail("storage_unavailable");
        }
      },
    }),
    async redeem(input = {}) {
      if (!input || typeof input !== "object") fail("invalid_pairing_input");
      const { code, devicePublicId } = input;
      if (
        typeof code !== "string" ||
        !/^[A-Za-z0-9_-]{32}$/.test(code) ||
        typeof devicePublicId !== "string" ||
        !/^[A-Za-z0-9._:-]{1,128}$/.test(devicePublicId)
      ) {
        fail("invalid_pairing_input");
      }
      return run(async () => {
        try {
          await clear();
        } catch {
          fail("storage_unavailable");
        }
        try {
          const reply = await post("redeem", {
            code,
            device_public_id: devicePublicId,
          });
          const connection = projection(reply, canvasOrigin, [
            "pending_identity",
          ]);
          if (
            typeof reply.ingestion_bearer !== "string" ||
            !secret.test(reply.ingestion_bearer) ||
            Date.parse(connection.credential_expires_at) <= Date.now()
          )
            throw Error();
          await storageArea.set({
            [key]: {
              schema_version: 1,
              api_origin: apiOrigin,
              connection,
              ingestion_bearer: reply.ingestion_bearer,
            },
          });
          return { ...connection };
        } catch (error) {
          return cleanup(
            error instanceof PairingClientError
              ? error.code
              : "pairing_outcome_unknown",
          );
        }
      });
    },
    async bindCurrentSession() {
      return run(async () => {
        const item = await record();
        if (
          !item ||
          Date.parse(item.connection.credential_expires_at) <= Date.now()
        )
          return cleanup("reconnect_required");
        let before;
        try {
          before = await subject();
        } catch {
          fail("canvas_session_unavailable");
        }
        try {
          const reply = await post(
            "bind",
            { origin: canvasOrigin, provider_subject: before },
            item.ingestion_bearer,
          );
          const connection = projection(reply, canvasOrigin, ["connected"]);
          if (
            connection.connection_id !== item.connection.connection_id ||
            connection.generation !== item.connection.generation ||
            Date.parse(connection.credential_expires_at) <= Date.now()
          )
            throw Error();
          const after = await subject();
          if (after !== before) {
            try {
              await post(
                "bind",
                { origin: canvasOrigin, provider_subject: after },
                item.ingestion_bearer,
              );
            } catch {
              /* Server fence outcome can be unknown; local state is always discarded. */
            }
            return cleanup("canvas_account_changed");
          }
          await storageArea.set({ [key]: { ...item, connection } });
          return { ...connection };
        } catch (error) {
          return cleanup(
            error instanceof PairingClientError
              ? error.code
              : "binding_outcome_unknown",
          );
        }
      });
    },
    async readCurrentContext() {
      return run(() => currentContext());
    },
    async readCachedConnection() {
      return run(async () => {
        const item = await record();
        if (!item) return null;
        return {
          ...item.connection,
          ...(Date.parse(item.connection.credential_expires_at) <= Date.now()
            ? { state: "reconnect_required" }
            : {}),
        };
      });
    },
  });
}
