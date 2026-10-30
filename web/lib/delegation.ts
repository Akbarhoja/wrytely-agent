import { api, ApiError } from "./client";

export type PrivateDraftDecision = Readonly<{
  key: string;
  objective: string;
  source_ids: readonly string[];
  confirm_private_draft: true;
}>;
export type PrivateDraftReceipt = { responsibility_id: string; requested_mode: "private_draft" };
export type DraftStatus = {
  responsibility_id: string;
  requested_mode: "analysis" | "private_draft";
  status: "active" | "blocked" | "done";
  reason: null | "source_changed" | "draft_policy_or_rubric_blocked" | "draft_work_blocked";
  assessment_state: "not_requested" | "pending" | "assessed" | "blocked";
  workflow_state:
    "not_requested" | "pending" | "queued" | "running" | "ready_for_review" | "blocked";
  artifact_id: string | null;
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function createPrivateDraft(value: PrivateDraftDecision, signal: AbortSignal) {
  return api<PrivateDraftReceipt>("responsibilities", {
    method: "POST",
    headers: { "Idempotency-Key": value.key },
    body: JSON.stringify({
      objective: value.objective,
      source_ids: value.source_ids,
      confirm_private_draft: value.confirm_private_draft,
    }),
    signal,
  });
}
export async function loadDraftStatus(id: string, signal: AbortSignal): Promise<DraftStatus> {
  if (!uuid.test(id)) throw new ApiError(404, "Work not found.");
  const value = await api<DraftStatus>(`responsibilities/${id}/status`, { signal });
  if (
    !value ||
    value.responsibility_id !== id ||
    !["analysis", "private_draft"].includes(value.requested_mode) ||
    !["active", "blocked", "done"].includes(value.status) ||
    ![null, "source_changed", "draft_policy_or_rubric_blocked", "draft_work_blocked"].includes(
      value.reason,
    ) ||
    !["not_requested", "pending", "assessed", "blocked"].includes(value.assessment_state) ||
    !["not_requested", "pending", "queued", "running", "ready_for_review", "blocked"].includes(
      value.workflow_state,
    ) ||
    !(
      value.artifact_id === null ||
      (typeof value.artifact_id === "string" && uuid.test(value.artifact_id))
    )
  ) {
    throw new ApiError(502, "Work status response is unavailable.");
  }
  return value;
}
