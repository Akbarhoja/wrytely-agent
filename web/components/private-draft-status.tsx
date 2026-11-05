"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ApiError } from "../lib/client";
import { loadDraftStatus, type DraftStatus } from "../lib/delegation";

type Props = {
  responsibilityId: string;
  enabled?: boolean;
  onSessionExpired?: () => void;
  onViewResults?: () => void;
  onStatus?: (status: DraftStatus) => void;
};
export function PrivateDraftStatus({ responsibilityId, ...props }: Props) {
  return <StatusSession key={responsibilityId} responsibilityId={responsibilityId} {...props} />;
}
function StatusSession({
  responsibilityId,
  enabled = true,
  onSessionExpired,
  onViewResults,
  onStatus,
}: Props) {
  const heading = useId();
  const [value, setValue] = useState<DraftStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [expired, setExpired] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const expire = useRef(onSessionExpired);
  expire.current = onSessionExpired;
  const notify = useRef(onStatus);
  notify.current = onStatus;
  async function refresh(signal: AbortSignal) {
    setValue(null);
    setError(false);
    setBusy(true);
    try {
      const next = await loadDraftStatus(responsibilityId, signal);
      if (!signal.aborted) {
        setValue(next);
        notify.current?.(next);
      }
    } catch (failure) {
      if (signal.aborted) return;
      if (failure instanceof ApiError && failure.status === 401) {
        setValue(null);
        setExpired(true);
        expire.current?.();
      } else setError(true);
    } finally {
      if (!signal.aborted) setBusy(false);
    }
  }
  useEffect(() => {
    const current = new AbortController();
    controller.current = current;
    if (enabled) void refresh(current.signal);
    return () => controller.current?.abort();
  }, [enabled]);
  let title = "Work status";
  let description = "Refresh to read the saved status. This does not start or retry work.";
  if (value && enabled) {
    if (value.reason === "source_changed") {
      title = "Source context changed";
      description =
        "The saved permission cannot be reused for changed evidence. Review the sources before deciding on new work.";
    } else if (
      value.reason === "draft_policy_or_rubric_blocked" ||
      value.assessment_state === "blocked"
    ) {
      title = "Policy or requirements need attention";
      description =
        "Drafting is blocked. Review the saved assignment, policy and requirements; source text cannot authorize work by itself.";
    } else if (value.status === "blocked" || value.workflow_state === "blocked") {
      title = "Private work needs attention";
      description =
        "The saved workflow is blocked. Review any available draft and checks before deciding what to do next.";
    } else if (value.requested_mode === "analysis") {
      title = "Analysis only";
      description = "This work has no private-draft authorization.";
    } else if (value.workflow_state === "ready_for_review" && value.artifact_id) {
      title = "Draft ready for your review";
      description =
        "Open Private results to inspect the saved draft, citations and checks. You still need to review it.";
    } else if (value.workflow_state === "running") {
      title = "Private draft in progress";
      description = "The saved workflow is running. Refresh for an updated status.";
    } else if (value.workflow_state === "queued") {
      title = "Private draft queued";
      description = "The draft task is saved. Paused work waits until you resume the agent.";
    } else {
      title = "Waiting for policy and requirements checks";
      description =
        "Your private request is saved. Consent alone does not establish that drafting is permitted or that a draft is ready.";
    }
  }
  if (expired)
    return (
      <div className="academic-detail">
        <p>Your session expired. Work status has been cleared.</p>
        <a href="/sign-in">Sign in again</a>
      </div>
    );
  return (
    <section className="academic-detail" aria-labelledby={heading}>
      <div className="section-heading">
        <h3 id={heading}>{title}</h3>
        <button
          className="quiet-button"
          disabled={busy || !enabled}
          onClick={() => {
            controller.current?.abort();
            const next = new AbortController();
            controller.current = next;
            void refresh(next.signal);
          }}
        >
          Refresh work status
        </button>
      </div>
      {busy ? (
        <p role="status">Loading work status…</p>
      ) : error ? (
        <p role="alert" className="connection-error">
          Work status could not be loaded. Refresh to try again.
        </p>
      ) : (
        <p>{description}</p>
      )}
      {value && enabled && (
        <p className="subtle">
          Status does not authorize sharing, sending or submission. Read the draft and its checks in
          Private results.
        </p>
      )}
      {onViewResults && (
        <button className="quiet-button" onClick={onViewResults}>
          View private results
        </button>
      )}
    </section>
  );
}
