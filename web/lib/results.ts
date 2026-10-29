import { api, ApiError } from "./client";

export type Responsibility = {
  id: string;
  objective: string;
  status: "active" | "blocked" | "done";
  steps_created: number;
  max_steps: number;
  created_at: string;
};
export type SavedDraft = {
  id: string;
  task_id: string;
  title: string;
  state: "review" | "needs_revision" | "ready";
  stale: boolean;
  created_at: string;
};
type Evidence = { version_id: string; quote: string };
type Assessment = {
  reason: string;
  claim_support: string[];
  rubric_coverage: string[];
  policy_allows_drafting: boolean;
  disclosure_satisfied: boolean;
  rubric_complete: boolean;
  uncited_claims: boolean;
};
export type DraftReview = {
  artifact: {
    id: string;
    responsibility_id: string;
    task_id: string;
    state: SavedDraft["state"];
    stale: boolean;
    created_at: string;
    memory_revision: number;
    draft: {
      title: string;
      body: string;
      disclosure: string;
      citations: (Evidence & { claim: string })[];
    };
  };
  latest_check: null | {
    passed: boolean;
    errors: string[];
    assessment: Assessment | null;
    policy: Evidence & { status: string };
    rubric: Evidence[];
    limits: string;
  };
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const isId = (value: unknown) => typeof value === "string" && uuid.test(value);
const text = (value: unknown, max: number) => typeof value === "string" && value.length <= max;
const date = (value: unknown) => typeof value === "string" && Number.isFinite(Date.parse(value));
const states = ["review", "needs_revision", "ready"];
function invalid(): never {
  throw new ApiError(502, "Saved result response is unavailable.");
}
function evidence(value: Evidence) {
  return value && isId(value.version_id) && text(value.quote, 2000);
}

export async function listWork(signal: AbortSignal): Promise<Responsibility[]> {
  const value = await api<{ responsibilities: Responsibility[]; limit: number }>(
    "responsibilities",
    { signal },
  );
  if (
    value?.limit !== 50 ||
    !Array.isArray(value.responsibilities) ||
    value.responsibilities.length > 50
  )
    invalid();
  for (const row of value.responsibilities) {
    if (
      !row ||
      !isId(row.id) ||
      !text(row.objective, 12000) ||
      !["active", "blocked", "done"].includes(row.status) ||
      !Number.isInteger(row.steps_created) ||
      !Number.isInteger(row.max_steps) ||
      !date(row.created_at)
    )
      invalid();
  }
  return value.responsibilities;
}
export async function listDrafts(id: string, signal: AbortSignal): Promise<SavedDraft[]> {
  if (!isId(id)) invalid();
  const value = await api<{ artifacts: SavedDraft[]; limit: number }>(
    `responsibilities/${id}/artifacts`,
    { signal },
  );
  if (value?.limit !== 50 || !Array.isArray(value.artifacts) || value.artifacts.length > 50)
    invalid();
  for (const row of value.artifacts) {
    if (
      !row ||
      !isId(row.id) ||
      !isId(row.task_id) ||
      !text(row.title, 300) ||
      !states.includes(row.state) ||
      typeof row.stale !== "boolean" ||
      !date(row.created_at)
    )
      invalid();
  }
  return value.artifacts;
}
export async function loadReview(id: string, signal: AbortSignal): Promise<DraftReview> {
  if (!isId(id)) invalid();
  const value = await api<DraftReview>(`artifacts/${id}`, { signal });
  const item = value?.artifact;
  if (
    !item ||
    item.id !== id ||
    !isId(item.responsibility_id) ||
    !isId(item.task_id) ||
    !states.includes(item.state) ||
    typeof item.stale !== "boolean" ||
    !Number.isInteger(item.memory_revision) ||
    !date(item.created_at)
  )
    invalid();
  const draft = item.draft;
  if (
    !draft ||
    !text(draft.title, 300) ||
    !text(draft.body, 24000) ||
    !text(draft.disclosure, 2000) ||
    !Array.isArray(draft.citations) ||
    draft.citations.length > 30 ||
    !draft.citations.every((c) => evidence(c) && text(c.claim, 2000))
  )
    invalid();
  const report = value.latest_check;
  if (report !== null) {
    if (
      !report ||
      typeof report.passed !== "boolean" ||
      !Array.isArray(report.errors) ||
      report.errors.length > 100 ||
      !report.errors.every((e) => text(e, 200)) ||
      !evidence(report.policy) ||
      !["permitted", "disclosure_required", "limited", "prohibited", "unknown"].includes(
        report.policy.status,
      ) ||
      !Array.isArray(report.rubric) ||
      report.rubric.length > 30 ||
      !report.rubric.every(evidence) ||
      !text(report.limits, 4000)
    )
      invalid();
    const assessment = report.assessment;
    if (assessment !== null) {
      if (
        !assessment ||
        !text(assessment.reason, 3000) ||
        !Array.isArray(assessment.claim_support) ||
        assessment.claim_support.length > 30 ||
        !assessment.claim_support.every((s) =>
          ["supported", "unsupported", "uncertain"].includes(s),
        ) ||
        !Array.isArray(assessment.rubric_coverage) ||
        assessment.rubric_coverage.length > 30 ||
        !assessment.rubric_coverage.every((s) => ["covered", "missing", "uncertain"].includes(s)) ||
        [
          assessment.policy_allows_drafting,
          assessment.disclosure_satisfied,
          assessment.rubric_complete,
          assessment.uncited_claims,
        ].some((v) => typeof v !== "boolean")
      )
        invalid();
    }
  }
  return value;
}

export function reviewState(review: DraftReview) {
  if (review.artifact.stale) return "Source context changed";
  if (!review.latest_check) return "Not yet checked";
  if (
    !review.latest_check.passed ||
    review.latest_check.errors.length > 0 ||
    review.artifact.state !== "ready"
  )
    return "Checks need attention";
  return "Ready for your review";
}
