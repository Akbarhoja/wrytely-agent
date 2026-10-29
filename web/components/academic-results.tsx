"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "../lib/client";
import {
  listWork,
  listDrafts,
  loadReview,
  reviewState,
  type Responsibility,
  type SavedDraft,
  type DraftReview,
} from "../lib/results";

const findings: Record<string, string> = {
  policy_evidence_missing_or_stale: "Policy evidence is missing or needs a freshness review.",
  course_policy_not_permitting_draft: "The recorded policy does not permit this draft.",
  disclosure_missing_from_body: "The required disclosure is missing from the draft body.",
  citations_missing: "The draft has no citations.",
  citation_missing_or_stale: "A quotation is missing from its source or needs a freshness review.",
  cited_claim_not_in_draft: "A cited claim does not appear in the draft.",
  rubric_evidence_missing_or_stale: "A requirement lacks current source evidence.",
  invalid_assessment: "A complete review could not be recorded.",
  assessment_coverage_mismatch: "The review does not cover every citation and requirement.",
  claims_not_supported: "Some claims are unsupported or uncertain.",
  rubric_not_covered: "Some requirements are missing or uncertain.",
  policy_assessment_failed: "The reviewer did not confirm that policy allows this draft.",
  disclosure_assessment_failed: "The reviewer did not confirm the required disclosure.",
  rubric_incomplete: "The requirement list may be incomplete.",
  uncited_claims: "The reviewer found claims that need citations.",
};
const workState = { active: "Work in progress", blocked: "Work blocked", done: "Work finished" };

export function AcademicResults({
  userId,
  enabled = true,
}: {
  userId?: string;
  enabled?: boolean;
}) {
  if (!userId)
    return (
      <section className="connections-panel academic-panel">
        <h2>Private results</h2>
        <p>Sign in to inspect your saved drafts and checks.</p>
      </section>
    );
  return <ResultSession key={userId} enabled={enabled} />;
}

function ResultSession({ enabled }: { enabled: boolean }) {
  const [work, setWork] = useState<Responsibility[] | null>(null);
  const [selected, setSelected] = useState<Responsibility | null>(null);
  const [drafts, setDrafts] = useState<SavedDraft[] | null>(null);
  const [review, setReview] = useState<DraftReview | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  const active = () => controller.current && !controller.current.signal.aborted;
  function failed(failure: unknown, message: string) {
    if (failure instanceof ApiError && failure.status === 401) {
      controller.current?.abort();
      setWork(null);
      setSelected(null);
      setDrafts(null);
      setReview(null);
      setExpired(true);
    } else setError(message);
  }
  async function refresh() {
    if (!enabled || !active()) return;
    const request = ++sequence.current;
    setBusy("Loading saved work…");
    setError(null);
    setSelected(null);
    setDrafts(null);
    setReview(null);
    setWork(null);
    try {
      const rows = await listWork(controller.current!.signal);
      if (active() && request === sequence.current) setWork(rows);
    } catch (failure) {
      if (active() && request === sequence.current)
        failed(failure, "Saved work could not be loaded. Refresh results to try again.");
    } finally {
      if (active() && request === sequence.current) setBusy(null);
    }
  }
  useEffect(() => {
    controller.current = new AbortController();
    return () => {
      controller.current?.abort();
    };
  }, []);
  useEffect(() => {
    if (enabled && !expired) void refresh();
  }, [enabled, expired]);
  useEffect(() => {
    if (review) reviewHeading.current?.focus();
  }, [review]);

  async function openWork(row: Responsibility) {
    const request = ++sequence.current;
    setSelected(row);
    setDrafts(null);
    setReview(null);
    setError(null);
    setBusy("Loading saved drafts…");
    try {
      const rows = await listDrafts(row.id, controller.current!.signal);
      if (active() && request === sequence.current) setDrafts(rows);
    } catch (failure) {
      if (active() && request === sequence.current)
        failed(failure, "Saved drafts could not be loaded. Select the work again to retry.");
    } finally {
      if (active() && request === sequence.current) setBusy(null);
    }
  }
  async function openDraft(id: string) {
    if (!selected) return;
    const duty = selected.id;
    const request = ++sequence.current;
    setReview(null);
    setError(null);
    setBusy("Opening draft…");
    try {
      const result = await loadReview(id, controller.current!.signal);
      if (result.artifact.responsibility_id !== duty) throw new ApiError(502, "Result mismatch");
      if (active() && request === sequence.current) setReview(result);
    } catch (failure) {
      if (active() && request === sequence.current)
        failed(failure, "Draft could not be opened. Select it again to retry.");
    } finally {
      if (active() && request === sequence.current) setBusy(null);
    }
  }

  if (expired)
    return (
      <section className="connections-panel academic-panel">
        <h2>Private results</h2>
        <p>Your session expired. Private results have been cleared from this view.</p>
        <a className="quiet-button" href="/sign-in">
          Sign in again
        </a>
      </section>
    );
  return (
    <div className="connections-layout">
      <section className="connections-panel academic-panel" aria-labelledby="private-work-title">
        <div className="section-heading">
          <h2 id="private-work-title">Your delegated work</h2>
          <button
            className="quiet-button"
            disabled={Boolean(busy) || !enabled}
            onClick={() => void refresh()}
          >
            Refresh results
          </button>
        </div>
        <p className="body-copy">
          Inspect saved drafts and their checks before using them. Nothing is shared, sent or
          submitted from this view.
        </p>
        <p className="subtle">
          Latest 50 responsibilities; each work item shows up to 50 saved drafts.
        </p>
        {!enabled && <p role="status">Connect your workspace to load private results.</p>}
        {busy && <p role="status">{busy}</p>}
        {error && (
          <p className="connection-error" role="alert">
            {error}
          </p>
        )}
        {work?.length === 0 && !busy && !error && <p>No delegated work yet.</p>}
        <ul className="academic-sources">
          {work?.map((row) => (
            <li key={row.id}>
              <button
                className="academic-source-button"
                disabled={!enabled}
                onClick={() => void openWork(row)}
                aria-label={`Open work: ${row.objective}`}
                aria-pressed={selected?.id === row.id}
              >
                <strong>{row.objective}</strong>
                <span>{workState[row.status]}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      {selected && (
        <section className="connections-panel academic-panel" aria-labelledby="saved-drafts-title">
          <div className="section-heading">
            <h2 id="saved-drafts-title">Saved drafts</h2>
            <span>{workState[selected.status]}</span>
          </div>
          <p className="body-copy">{selected.objective}</p>
          {drafts?.length === 0 && (
            <p>No saved drafts yet. Work may still be in progress or blocked.</p>
          )}
          <ul className="academic-sources">
            {drafts?.map((row) => (
              <li key={row.id}>
                <button
                  className="academic-source-button"
                  disabled={!enabled}
                  onClick={() => void openDraft(row.id)}
                  aria-label={`Open draft: ${row.title}`}
                  aria-pressed={review?.artifact.id === row.id}
                >
                  <strong>{row.title}</strong>
                  <span>
                    {row.stale
                      ? "Source context changed"
                      : row.state === "needs_revision"
                        ? "Needs revision"
                        : row.state === "review"
                          ? "Awaiting checks"
                          : "Saved draft — inspect checks"}{" "}
                    · {new Date(row.created_at).toLocaleString("en-US")}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {review && (
        <section
          className="connections-panel academic-panel result-review"
          aria-label="Private draft and checks"
        >
          <h2 ref={reviewHeading} tabIndex={-1}>
            {reviewState(review)}
          </h2>
          {review.artifact.stale && (
            <p className="result-caution">
              The source context changed after this draft was saved. Inspect the current
              requirements before using it.
            </p>
          )}
          <p className="subtle">
            {review.latest_check?.passed
              ? review.artifact.stale
                ? "Historical checks passed; this draft is no longer current."
                : "Stored checks passed. Student review is still required."
              : review.latest_check
                ? "Stored checks found issues. This is not a cleared result."
                : "No completed check report is saved for this draft."}
          </p>
          <article className="academic-detail">
            <h3>{review.artifact.draft.title}</h3>
            <pre>{review.artifact.draft.body}</pre>
            {review.artifact.draft.disclosure && (
              <>
                <h3>Disclosure</h3>
                <p className="result-text">{review.artifact.draft.disclosure}</p>
              </>
            )}
          </article>
          <section className="academic-detail" aria-label="Citation evidence">
            <h3>Citation evidence</h3>
            {review.artifact.draft.citations.length === 0 && <p>No citations were saved.</p>}
            <ol className="result-evidence">
              {review.artifact.draft.citations.map((item, index) => (
                <li key={index}>
                  <p>{item.claim}</p>
                  <blockquote>{item.quote}</blockquote>
                  <p className="subtle">Stored source version: {item.version_id}</p>
                </li>
              ))}
            </ol>
          </section>
          <section className="academic-detail" aria-label="Stored verification checks">
            <h3>Stored checks</h3>
            {review.latest_check ? (
              <>
                <ul>
                  {[...new Set(review.latest_check.errors)].map((code) => (
                    <li key={code}>
                      {findings[code] || "An additional stored check needs attention."}
                    </li>
                  ))}
                </ul>
                {review.latest_check.assessment && (
                  <>
                    <p className="result-text">{review.latest_check.assessment.reason}</p>
                    <p>
                      Claims:{" "}
                      {review.latest_check.assessment.claim_support.join(", ") || "None assessed"}.
                      Requirements:{" "}
                      {review.latest_check.assessment.rubric_coverage.join(", ") || "None assessed"}
                      .
                    </p>
                  </>
                )}
                <p className="result-caution">
                  Model assessments are fallible. A passed check does not mean this work was
                  submitted or approved.
                </p>
                <details>
                  <summary>Policy and requirement evidence</summary>
                  <p>Recorded policy: {review.latest_check.policy.status.replaceAll("_", " ")}</p>
                  <blockquote>{review.latest_check.policy.quote}</blockquote>
                  <p className="subtle">
                    Stored source version: {review.latest_check.policy.version_id}
                  </p>
                  <ol className="result-evidence">
                    {review.latest_check.rubric.map((item, index) => (
                      <li key={index}>
                        <blockquote>{item.quote}</blockquote>
                        <p className="subtle">Stored source version: {item.version_id}</p>
                      </li>
                    ))}
                  </ol>
                </details>
              </>
            ) : (
              <p>Checks are pending or unavailable. Readiness has not been established.</p>
            )}
          </section>
        </section>
      )}
    </div>
  );
}
