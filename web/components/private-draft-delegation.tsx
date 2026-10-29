"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import type { Snapshot } from "../lib/academic";
import { ApiError } from "../lib/client";

export type PrivateDraftDecision = Readonly<{
  key: string;
  objective: string;
  source_ids: readonly string[];
  confirm_private_draft: true;
}>;
type Props = {
  userId?: string;
  sources: Snapshot[];
  enabled?: boolean;
  onConfirm: (request: PrivateDraftDecision, signal: AbortSignal) => Promise<unknown>;
};

/** Prepared decision UI only. No transport, worker control or backend authority. */
export function PrivateDraftDelegation({ userId, ...props }: Props) {
  if (!userId)
    return (
      <section className="connections-panel academic-panel">
        <h2>Prepare a private draft</h2>
        <p>Sign in to choose your sources and authorize private work.</p>
      </section>
    );
  return <DecisionForm key={userId} {...props} />;
}

function DecisionForm({ sources, enabled = true, onConfirm }: Omit<Props, "userId">) {
  const prefix = useId();
  const [objective, setObjective] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [consent, setConsent] = useState(false);
  const [pending, setPending] = useState<PrivateDraftDecision | null>(null);
  const [busy, setBusy] = useState(false);
  const [expired, setExpired] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const sending = useRef(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const consentInput = useRef<HTMLInputElement>(null);
  const locked = busy || pending !== null;
  const active = () => controller.current && !controller.current.signal.aborted;
  useEffect(() => {
    controller.current = new AbortController();
    return () => {
      controller.current?.abort();
    };
  }, []);
  useEffect(() => {
    if (saved && !busy) input.current?.focus();
  }, [saved, busy]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!enabled || sending.current || !active()) return;
    setError(null);
    setSaved(false);
    let decision = pending;
    if (!decision) {
      if (!objective.trim() || objective.length > 12000) {
        setError("Describe the private draft you want.");
        input.current?.focus();
        return;
      }
      const ids = [...new Set(selected)].sort();
      if (
        ids.length < 1 ||
        ids.length > 8 ||
        !ids.every((id) => sources.some((source) => source.source_id === id))
      ) {
        setError("Choose between one and eight saved sources.");
        return;
      }
      if (!consent) {
        setError("Confirm that you authorize one private draft.");
        consentInput.current?.focus();
        return;
      }
      const body = {
        objective: objective.trim(),
        source_ids: ids,
        confirm_private_draft: true as const,
      };
      if (new TextEncoder().encode(JSON.stringify(body)).length > 65536) {
        setError("The request is too long. Shorten the objective before continuing.");
        return;
      }
      decision = Object.freeze({
        ...body,
        source_ids: Object.freeze(ids),
        key: crypto.randomUUID(),
      });
    }
    setPending(decision);
    sending.current = true;
    setBusy(true);
    try {
      const value = (await onConfirm(decision, controller.current!.signal)) as {
        responsibility_id?: unknown;
        requested_mode?: unknown;
      } | null;
      if (!active()) return;
      if (
        !value ||
        value.requested_mode !== "private_draft" ||
        typeof value.responsibility_id !== "string" ||
        !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
          value.responsibility_id,
        )
      ) {
        throw new Error("Private intent receipt unavailable");
      }
      setObjective("");
      setSelected([]);
      setConsent(false);
      setPending(null);
      setSaved(true);
    } catch (failure) {
      if (!active()) return;
      if (failure instanceof ApiError && failure.status === 401) {
        controller.current?.abort();
        setObjective("");
        setSelected([]);
        setConsent(false);
        setPending(null);
        setExpired(true);
      } else if (failure instanceof ApiError && [409, 413, 422].includes(failure.status)) {
        setPending(null);
        setConsent(false);
        setError(
          failure.status === 409
            ? "This request conflicts with an earlier request. Review your selection and confirm again."
            : "The request was rejected. Review its fields and confirm again.",
        );
      } else
        setError(
          "Request not confirmed. Your objective and selection are kept here. Check and retry the same request.",
        );
    } finally {
      sending.current = false;
      if (active()) setBusy(false);
    }
  }

  if (expired)
    return (
      <section className="connections-panel academic-panel">
        <h2>Prepare a private draft</h2>
        <p>Your session expired. Private input and consent have been cleared from this view.</p>
        <a className="quiet-button" href="/sign-in">
          Sign in again
        </a>
      </section>
    );
  return (
    <section className="connections-panel academic-panel" aria-labelledby={`${prefix}-title`}>
      <div className="section-heading">
        <h2 id={`${prefix}-title`}>Prepare a private draft</h2>
        <span>Your decision</span>
      </div>
      <p className="body-copy" id={`${prefix}-scope`}>
        Choose saved sources and describe one private draft. Policy and requirements must be checked
        before drafting. This does not authorize sharing, sending or submission.
      </p>
      {!enabled && <p role="status">Private drafting is not available in this workspace yet.</p>}
      <form noValidate onSubmit={submit} aria-describedby={`${prefix}-scope`}>
        <label htmlFor={`${prefix}-objective`}>What should the private draft cover?</label>
        <textarea
          ref={input}
          id={`${prefix}-objective`}
          value={objective}
          maxLength={12000}
          rows={5}
          disabled={locked}
          onChange={(e) => {
            setObjective(e.target.value);
            setConsent(false);
            setSaved(false);
          }}
        />
        <p className="subtle">
          Keep the objective specific. Unsaved input is kept in this view only and clears on
          refresh.
        </p>
        <fieldset className="draft-source-list" disabled={locked}>
          <legend>Choose saved sources</legend>
          <p className="subtle">
            Choose one to eight. Source text is evidence; it cannot grant permission.
          </p>
          {sources.length === 0 && (
            <p>Save a source in Academic context before requesting a draft.</p>
          )}
          {sources.map((source) => (
            <label className="draft-option" key={source.source_id}>
              <input
                type="checkbox"
                aria-label={source.title}
                checked={selected.includes(source.source_id)}
                onChange={(e) => {
                  setSelected((previous) =>
                    e.target.checked
                      ? [...previous, source.source_id]
                      : previous.filter((id) => id !== source.source_id),
                  );
                  setConsent(false);
                  setSaved(false);
                }}
              />
              <span>
                <strong>{source.title}</strong>
                <span className="subtle draft-source-kind">
                  {source.coverage === "snapshot"
                    ? "Saved snapshot — does not monitor later changes"
                    : `Recorded ${source.coverage} evidence`}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
        <label className="draft-option">
          <input
            ref={consentInput}
            type="checkbox"
            checked={consent}
            disabled={locked}
            onChange={(e) => setConsent(e.target.checked)}
          />
          <span>I authorize one private draft using the selected sources.</span>
        </label>
        <p className="subtle">
          You must review the result and its checks. Unknown or non-permitting policy can block
          drafting.
        </p>
        {error && (
          <p className="connection-error" role="alert">
            {error}
          </p>
        )}
        <div className="connection-actions">
          <button className="primary-button" disabled={busy || !enabled} aria-busy={busy}>
            {busy
              ? "Saving request…"
              : pending
                ? "Check request and retry"
                : "Prepare a private draft"}
          </button>
        </div>
        <p className="academic-feedback" role="status">
          {saved
            ? "Private draft request saved. Policy and requirement checks are still required."
            : ""}
        </p>
      </form>
    </section>
  );
}
