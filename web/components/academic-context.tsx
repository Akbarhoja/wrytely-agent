"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "../lib/client";
import { createPrivateDraft } from "../lib/delegation";
import { PrivateDraftDelegation } from "./private-draft-delegation";
import { PrivateDraftStatus } from "./private-draft-status";
import {
  listSnapshots,
  loadSnapshot,
  saveSnapshot,
  type Snapshot,
  type SnapshotDetail,
  type SnapshotSave,
} from "../lib/academic";

export function AcademicContext({
  userId,
  enabled = true,
  onViewResults,
  onSessionExpired,
}: {
  userId?: string;
  enabled?: boolean;
  onViewResults?: () => void;
  onSessionExpired?: () => void;
}) {
  if (!userId)
    return (
      <section className="connections-panel academic-panel">
        <h2>Your academic context</h2>
        <p>Sign in to save private assignment and source snapshots.</p>
      </section>
    );
  // A changed identity destroys the entire private state before its next paint.
  return (
    <SnapshotSession
      key={userId}
      userId={userId}
      enabled={enabled}
      onViewResults={onViewResults}
      onSessionExpired={onSessionExpired}
    />
  );
}

function SnapshotSession({
  enabled,
  userId,
  onViewResults,
  onSessionExpired,
}: {
  enabled: boolean;
  userId: string;
  onViewResults?: () => void;
  onSessionExpired?: () => void;
}) {
  const [responsibilityId, setResponsibilityId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [rows, setRows] = useState<Snapshot[] | null>(null);
  const [selected, setSelected] = useState<SnapshotDetail | null>(null);
  const [listError, setListError] = useState(false);
  const [detailError, setDetailError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [opening, setOpening] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [pending, setPending] = useState<SnapshotSave | null>(null);
  const controller = useRef<AbortController | null>(null);
  const detailRequest = useRef(0);
  const listRequest = useRef(0);
  const saving = useRef(false);
  const titleInput = useRef<HTMLInputElement>(null);
  const textInput = useRef<HTMLTextAreaElement>(null);
  const signal = () => controller.current!.signal;
  const active = () => controller.current && !controller.current.signal.aborted;
  useEffect(() => {
    if (!busy && message) titleInput.current?.focus();
  }, [busy, message]);

  function sessionFailure(failure: unknown) {
    if (failure instanceof ApiError && failure.status === 401) {
      controller.current?.abort();
      setTitle("");
      setContent("");
      setRows(null);
      setSelected(null);
      setPending(null);
      setExpired(true);
      onSessionExpired?.();
      return true;
    }
    return false;
  }
  async function refresh() {
    if (!enabled || !active()) return;
    const request = ++listRequest.current;
    setLoading(true);
    setListError(false);
    try {
      const next = await listSnapshots(signal());
      if (active() && request === listRequest.current) setRows(next);
    } catch (failure) {
      if (active() && request === listRequest.current && !sessionFailure(failure))
        setListError(true);
    } finally {
      if (active() && request === listRequest.current) setLoading(false);
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
  }, [enabled, expired]); // account lifetime is keyed above

  async function open(id: string) {
    const request = ++detailRequest.current;
    setSelected(null);
    setDetailError(false);
    setOpening(id);
    try {
      const next = await loadSnapshot(id, signal());
      if (active() && request === detailRequest.current) setSelected(next);
    } catch (failure) {
      if (active() && request === detailRequest.current && !sessionFailure(failure))
        setDetailError(true);
    } finally {
      if (active() && request === detailRequest.current) setOpening(null);
    }
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (saving.current || !enabled || !active()) return;
    setError(null);
    setMessage("");
    if (!title.trim() || !content.trim()) {
      setError("Add a title and some text before saving.");
      (!title.trim() ? titleInput.current : textInput.current)?.focus();
      return;
    }
    if (
      title.length > 300 ||
      content.length > 24000 ||
      new TextEncoder().encode(JSON.stringify({ title, content })).length > 65536
    ) {
      setError("This snapshot is too long. Paste a shorter excerpt (up to 24,000 characters).");
      textInput.current?.focus();
      return;
    }
    const submission = pending || { title, content, key: crypto.randomUUID() };
    setPending(submission);
    saving.current = true;
    setBusy(true);
    try {
      const saved = await saveSnapshot(submission, signal());
      if (!active()) return;
      ++detailRequest.current;
      setOpening(null);
      setDetailError(false);
      setSelected(saved);
      setRows((previous) =>
        [saved, ...(previous || []).filter((row) => row.source_id !== saved.source_id)].slice(
          0,
          50,
        ),
      );
      setTitle("");
      setContent("");
      setPending(null);
      setMessage("Snapshot saved. No work has started.");
      // Fence an older index request from erasing this confirmed save.
      ++listRequest.current;
      setLoading(false);
      setListError(false);
    } catch (failure) {
      if (!active() || sessionFailure(failure)) return;
      if (failure instanceof ApiError && failure.status === 409) {
        setPending(null);
        setError(
          "This save conflicts with an earlier snapshot. Your text is kept; save it as a separate snapshot.",
        );
      } else if (failure instanceof ApiError && [413, 422].includes(failure.status)) {
        setPending(null);
        setError("This snapshot could not be saved. Check its length and fields.");
      } else
        setError(
          "Save not confirmed. Your text is kept here. Check and retry with the same request.",
        );
    } finally {
      saving.current = false;
      if (active()) setBusy(false);
    }
  }

  if (expired)
    return (
      <section className="connections-panel academic-panel">
        <h2>Your academic context</h2>
        <p>Your session expired. Private text has been cleared from this view.</p>
        <a className="quiet-button" href="/sign-in">
          Sign in again
        </a>
      </section>
    );
  return (
    <div className="connections-layout">
      <section className="connections-panel academic-panel" aria-labelledby="academic-title">
        <div className="section-heading">
          <h2 id="academic-title">Save the context behind your work</h2>
          <span>Private snapshots</span>
        </div>
        <p className="body-copy" id="snapshot-help">
          Paste an assignment, policy, source excerpt or a permitted group transcript. A saved
          snapshot does not monitor later changes. Saving does not start work or send a message.
        </p>
        {!enabled && <p role="status">Finish connecting your workspace before saving.</p>}
        <form noValidate onSubmit={save} aria-describedby="snapshot-help">
          <label htmlFor="snapshot-title">Snapshot title</label>
          <input
            id="snapshot-title"
            ref={titleInput}
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setMessage("");
            }}
            maxLength={300}
            disabled={busy || Boolean(pending)}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "snapshot-error" : undefined}
            placeholder="For example, DEMO 101 comparison rubric"
          />
          <label htmlFor="snapshot-content">Pasted text</label>
          <textarea
            id="snapshot-content"
            ref={textInput}
            value={content}
            onChange={(e) => {
              setContent(e.target.value);
              setMessage("");
            }}
            rows={9}
            maxLength={24000}
            disabled={busy || Boolean(pending)}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "snapshot-error" : "snapshot-count"}
          />
          <p className="subtle" id="snapshot-count">
            {content.length.toLocaleString("en-US")} / 24,000 characters · Unsaved text stays in
            this view. Refreshing or closing the page clears it. Use synthetic examples for testing.
          </p>
          {error && (
            <p className="connection-error" role="alert" id="snapshot-error">
              {error}
            </p>
          )}
          <div className="connection-actions">
            <button className="primary-button" disabled={busy || !enabled} aria-busy={busy}>
              {busy ? "Saving snapshot…" : pending ? "Check and retry save" : "Save snapshot"}
            </button>
          </div>
          <p className="academic-feedback" role="status">
            {message}
          </p>
        </form>
      </section>
      <section className="connections-panel academic-panel" aria-labelledby="saved-sources-title">
        <div className="section-heading">
          <h2 id="saved-sources-title">Saved context</h2>
          <button
            className="quiet-button"
            onClick={() => void refresh()}
            disabled={loading || !enabled}
          >
            Refresh snapshots
          </button>
        </div>
        <p className="subtle">
          Latest 50 sources, newest first. Open a source to read its saved text.
        </p>
        {loading && <p role="status">Loading saved snapshots…</p>}
        {listError && (
          <p className="connection-error" role="alert">
            Saved snapshots could not be loaded. Refresh to try again.
            {rows ? " Previously loaded sources are shown." : ""}
          </p>
        )}
        {rows?.length === 0 && !loading && !listError && <p>No saved snapshots yet.</p>}
        <ul className="academic-sources">
          {rows?.map((row) => (
            <li key={row.source_id}>
              <button
                className="academic-source-button"
                onClick={() => void open(row.source_id)}
                disabled={!enabled}
                aria-label={`Open ${row.title}`}
                aria-pressed={selected?.source_id === row.source_id}
              >
                <strong>{row.title}</strong>
                <span>
                  {row.coverage === "snapshot"
                    ? "Saved snapshot"
                    : `Recorded ${row.coverage} evidence`}{" "}
                  · {new Date(row.retrieved_at).toLocaleString("en-US")}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {opening && <p role="status">Opening saved text…</p>}
        {detailError && (
          <p className="connection-error" role="alert">
            This source could not be opened. Select it to try again.
          </p>
        )}
        {selected && (
          <article className="academic-detail" aria-label={`Saved text: ${selected.title}`}>
            <h3>{selected.title}</h3>
            <p className="subtle">
              {selected.coverage} · Revision {selected.external_revision}
            </p>
            <p className="subtle">Reference: {selected.reference}</p>
            <pre>{selected.content}</pre>
          </article>
        )}
      </section>
      <div className="academic-delegation">
        <PrivateDraftDelegation
          userId={userId}
          sources={rows || []}
          enabled={enabled && rows !== null && !loading && !listError}
          onConfirm={async (value, signal) => {
            try {
              return await createPrivateDraft(value, signal);
            } catch (failure) {
              if (active()) sessionFailure(failure);
              throw failure;
            }
          }}
          onSaved={(receipt) => setResponsibilityId(receipt.responsibility_id)}
        />
        {responsibilityId && (
          <PrivateDraftStatus
            responsibilityId={responsibilityId}
            enabled={enabled}
            onSessionExpired={() => sessionFailure(new ApiError(401, "Expired"))}
            onViewResults={onViewResults}
          />
        )}
      </div>
    </div>
  );
}
