export type Preparation = {
  id: string;
  created_at: string;
  key: string;
  object_id: string;
  title: string;
  kind: "preparation_checklist";
  notice: string;
  current: boolean;
  excerpts: { object_id: string; quote: string; kind: "review" | "student_action" }[];
  questions: string[];
  evidence: {
    object_id: string;
    observation_id: string;
    version_id: string | null;
    coverage: string;
    resource_coverage: string;
    missing: string[];
    unread_continuation: boolean;
  }[];
};

const uuid = (v: unknown): v is string =>
  typeof v === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v);
const object = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === "object" && !Array.isArray(v);
const text = (v: unknown, max: number): v is string =>
  typeof v === "string" && v.length <= max && v.trim().length > 0;
const list = (v: unknown, max: number): v is unknown[] => Array.isArray(v) && v.length <= max;

export function parsePreparations(value: unknown): Preparation[] {
  // An older backend may omit this additive field. Malformed new data is not an empty state.
  if (value === undefined) return [];
  const fail = () => {
    throw new Error("Preparation information unavailable");
  };
  if (!list(value, 20)) return fail();
  const ids = new Set(),
    keys = new Set();
  for (const p of value) {
    if (
      !object(p) ||
      !uuid(p.id) ||
      ids.has(p.id) ||
      !uuid(p.object_id) ||
      !text(p.key, 64) ||
      !/^[0-9a-f]{64}$/.test(p.key) ||
      keys.has(p.key) ||
      !text(p.created_at, 64) ||
      !Number.isFinite(Date.parse(p.created_at)) ||
      !text(p.title, 300) ||
      p.kind !== "preparation_checklist" ||
      !text(p.notice, 2000) ||
      typeof p.current !== "boolean" ||
      !list(p.evidence, 8) ||
      !p.evidence.length ||
      !list(p.excerpts, 8) ||
      !p.excerpts.length ||
      !list(p.questions, 5) ||
      !p.questions.every((q) => text(q, 500))
    )
      return fail();
    const sources = new Set();
    for (const pin of p.evidence) {
      if (
        !object(pin) ||
        !uuid(pin.object_id) ||
        sources.has(pin.object_id) ||
        !uuid(pin.observation_id) ||
        !(pin.version_id === null || uuid(pin.version_id)) ||
        !text(pin.coverage, 80) ||
        !text(pin.resource_coverage, 80) ||
        typeof pin.unread_continuation !== "boolean" ||
        !list(pin.missing, 50) ||
        !pin.missing.every((code) => text(code, 200))
      )
        return fail();
      sources.add(pin.object_id);
    }
    if (!sources.has(p.object_id)) return fail();
    for (const excerpt of p.excerpts) {
      if (
        !object(excerpt) ||
        !sources.has(excerpt.object_id) ||
        !text(excerpt.quote, 1500) ||
        !(excerpt.kind === "review" || excerpt.kind === "student_action")
      )
        return fail();
    }
    ids.add(p.id);
    keys.add(p.key);
  }
  return value as Preparation[];
}
