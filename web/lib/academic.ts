import { api, ApiError } from "./client";

export type Snapshot = {
  source_id: string;
  version_id: string;
  title: string;
  reference: string;
  coverage: "snapshot" | "api" | "feed" | "group";
  retrieved_at: string;
  external_revision: string;
};
export type SnapshotDetail = Snapshot & { content: string };
export type SnapshotSave = { key: string; title: string; content: string };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function snapshot(value: unknown): Snapshot {
  const item = value as Snapshot;
  if (
    !item ||
    !uuid.test(item.source_id) ||
    !uuid.test(item.version_id) ||
    typeof item.title !== "string" ||
    item.title.length > 300 ||
    typeof item.reference !== "string" ||
    typeof item.external_revision !== "string" ||
    !["snapshot", "api", "feed", "group"].includes(item.coverage) ||
    typeof item.retrieved_at !== "string" ||
    !Number.isFinite(Date.parse(item.retrieved_at))
  ) {
    throw new ApiError(502, "Saved source response is unavailable.");
  }
  return item;
}
function detail(value: unknown): SnapshotDetail {
  const item = snapshot(value) as SnapshotDetail;
  if (typeof item.content !== "string" || item.content.length > 24000)
    throw new ApiError(502, "Saved source text is unavailable.");
  return item;
}
export async function listSnapshots(signal: AbortSignal) {
  const value = await api<{ sources: unknown[]; limit: number }>("sources", { signal });
  if (value?.limit !== 50 || !Array.isArray(value.sources) || value.sources.length > 50)
    throw new ApiError(502, "Saved source list is unavailable.");
  return value.sources.map(snapshot);
}
export async function loadSnapshot(id: string, signal: AbortSignal) {
  if (!uuid.test(id)) throw new ApiError(404, "Source not found.");
  const item = detail(await api<unknown>(`sources/${id}`, { signal }));
  if (item.source_id !== id) throw new ApiError(502, "Saved source response is unavailable.");
  return item;
}
export async function saveSnapshot(value: SnapshotSave, signal: AbortSignal) {
  return detail(
    await api<unknown>("sources", {
      method: "POST",
      headers: { "Idempotency-Key": value.key },
      body: JSON.stringify({ title: value.title, content: value.content }),
      signal,
    }),
  );
}
