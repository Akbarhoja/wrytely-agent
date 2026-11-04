"use client";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/client";
import { ArtifactActions } from "./artifact-actions";
type Saved = { id: string; created_at: string; saved_state: string; memory_stale: boolean };
type Reference = { kind: "legacy" | "canvas_document"; quote: string };
type Detail = {
  schema_version: 2;
  artifact: {
    id: string;
    responsibility_id: string;
    memory_stale: boolean;
    draft: {
      title: string;
      body: string;
      disclosure: string;
      citations: { claim: string; evidence: Reference }[];
    };
  };
  controls: { agent_paused: boolean; responsibility_status: string };
  latest_check: null | {
    id: string;
    report: {
      passed: boolean;
      errors: string[];
      rubric: { evidence: Reference }[];
      limits: string;
    };
  };
  evidence_status: { state: string; reasons: string[] };
  limits: string;
};
type Original = {
  schema_version: 2;
  artifact_id: string;
  group: string;
  index: number;
  quote_matches: boolean;
  reference: Reference;
  source: {
    kind: "legacy" | "canvas_document";
    content?: string;
    sections?: { slot: number; page: number | null; text: string }[];
    next_slot?: number | null;
    missing?: string[];
  };
  evidence_status: { state: string; reasons: string[] };
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const status = (s: string) => s.replaceAll("_", " ");
export function DocumentResults({
  responsibilityId,
  enabled,
  onSessionExpired,
}: {
  responsibilityId: string;
  enabled: boolean;
  onSessionExpired: () => void;
}) {
  return (
    <DocumentSession
      key={responsibilityId}
      responsibilityId={responsibilityId}
      enabled={enabled}
      onSessionExpired={onSessionExpired}
    />
  );
}
function DocumentSession({
  responsibilityId,
  enabled,
  onSessionExpired,
}: {
  responsibilityId: string;
  enabled: boolean;
  onSessionExpired: () => void;
}) {
  const [rows, setRows] = useState<Saved[]>([]),
    [next, setNext] = useState<string | null>(null),
    [detail, setDetail] = useState<Detail | null>(null),
    [original, setOriginal] = useState<Original | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null),
    sequence = useRef(0);
  async function run(work: (signal: AbortSignal, current: () => boolean) => Promise<void>) {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    const revision = ++sequence.current;
    const current = () => !abort.signal.aborted && revision === sequence.current;
    setBusy(true);
    setError(null);
    setDetail(null);
    setOriginal(null);
    try {
      await work(abort.signal, current);
    } catch (e) {
      if (current()) {
        setDetail(null);
        setOriginal(null);
        setError(
          e instanceof ApiError && e.status === 409
            ? "Source access changed. Reconnect or sync Canvas, then reopen the draft."
            : "Could not open this private result. Refresh to try again.",
        );
        if (e instanceof ApiError && e.status === 401) {
          setRows([]);
          onSessionExpired();
        }
      }
    } finally {
      if (current()) setBusy(false);
    }
  }
  async function listing(signal: AbortSignal, current: () => boolean, before?: string) {
    const value = await api<{ schema_version: 2; artifacts: Saved[]; next: string | null }>(
      `v2/responsibilities/${responsibilityId}/artifacts${before ? `?before=${encodeURIComponent(before)}` : ""}`,
      { signal },
    );
    if (
      value.schema_version !== 2 ||
      !Array.isArray(value.artifacts) ||
      value.artifacts.some(
        (x) =>
          !uuid.test(x.id) ||
          typeof x.saved_state !== "string" ||
          !Number.isFinite(Date.parse(x.created_at)),
      )
    )
      throw Error();
    if (current()) {
      setRows((previous) => (before ? [...previous, ...value.artifacts] : value.artifacts));
      setNext(value.next);
    }
  }
  useEffect(() => {
    if (enabled) void run((signal, current) => listing(signal, current));
    else {
      controller.current?.abort();
      setDetail(null);
      setOriginal(null);
      setRows([]);
    }
    return () => {
      controller.current?.abort();
    };
  }, [enabled, responsibilityId]);
  async function open(id: string) {
    await run(async (signal, current) => {
      const value = await api<Detail>(`v2/artifacts/${id}`, { signal });
      if (
        value.schema_version !== 2 ||
        value.artifact.id !== id ||
        value.artifact.responsibility_id !== responsibilityId ||
        typeof value.artifact.draft.body !== "string" ||
        !Array.isArray(value.artifact.draft.citations)
      )
        throw Error();
      if (current()) setDetail(value);
    });
  }
  async function evidence(group: string, index: number, firstSlot = 0) {
    if (!detail) return;
    const saved = detail;
    await run(async (signal, current) => {
      const query = new URLSearchParams({ first_slot: String(firstSlot), limit: "1" });
      if (group !== "citation") {
        if (!saved.latest_check) throw Error();
        query.set("check_id", saved.latest_check.id);
      }
      const result = await api<Original>(
        `v2/artifacts/${saved.artifact.id}/evidence/${group}/${index}?${query}`,
        { signal },
      );
      if (
        result.schema_version !== 2 ||
        result.artifact_id !== saved.artifact.id ||
        result.group !== group ||
        result.index !== index ||
        typeof result.reference.quote !== "string"
      )
        throw Error();
      if (current()) {
        setDetail(saved);
        setOriginal(result);
      }
    });
  }
  return (
    <div className="document-results" aria-busy={busy}>
      <h3>Drafts using course documents</h3>
      <p>Open a draft to check current source access and inspect the original evidence.</p>
      <button
        className="quiet-button"
        disabled={busy || !enabled}
        onClick={() => void run((signal, current) => listing(signal, current))}
      >
        Refresh document drafts
      </button>
      {busy && <p role="status">Loading private result…</p>}
      {error && <p role="alert">{error}</p>}
      {!busy && !error && rows.length === 0 && (
        <p>No document-based drafts saved for this work yet.</p>
      )}
      <ul className="academic-sources">
        {rows.map((row) => (
          <li key={row.id}>
            <button
              className="academic-source-button"
              disabled={busy || !enabled}
              onClick={() => void open(row.id)}
            >
              <strong>Saved {new Date(row.created_at).toLocaleString()}</strong>
              <span>
                {row.memory_stale ? "Context changed" : status(row.saved_state)} · Inspect checks
              </span>
            </button>
          </li>
        ))}
      </ul>
      {next && (
        <button
          className="quiet-button"
          disabled={busy || !enabled}
          onClick={() => void run((signal, current) => listing(signal, current, next))}
        >
          More document drafts
        </button>
      )}
      {detail && (
        <article className="academic-detail">
          <h3>{detail.artifact.draft.title}</h3>
          <p>
            Current evidence: {status(detail.evidence_status.state)}
            {detail.artifact.memory_stale ? " · Context changed" : ""}
          </p>
          <p>
            {detail.latest_check?.report.passed
              ? "Checks passed when saved. Student review is still required."
              : "No passed check is available for this draft."}
          </p>
          <p>
            Agent {detail.controls.agent_paused ? "paused" : "not paused"}; work{" "}
            {status(detail.controls.responsibility_status)}. These inspection results do not
            authorize sending or submitting work.
          </p>
          {detail.evidence_status.reasons.length > 0 && (
            <ul>
              {detail.evidence_status.reasons.map((reason, i) => (
                <li key={i}>{status(reason)}</li>
              ))}
            </ul>
          )}
          <pre>{detail.artifact.draft.body}</pre>
          <ArtifactActions
            artifactId={detail.artifact.id}
            enabled={
              enabled &&
              !busy &&
              !!detail.latest_check?.report.passed &&
              !detail.artifact.memory_stale &&
              !detail.controls.agent_paused &&
              detail.evidence_status.state === "current"
            }
            onSessionExpired={onSessionExpired}
          />
          {detail.artifact.draft.disclosure && (
            <>
              <h4>Disclosure</h4>
              <p>{detail.artifact.draft.disclosure}</p>
            </>
          )}
          <h4>Sources</h4>
          {detail.artifact.draft.citations.map((citation, index) => (
            <div key={index}>
              <p>{citation.claim}</p>
              <blockquote>{citation.evidence.quote}</blockquote>
              <button
                className="quiet-button"
                disabled={busy || !enabled}
                onClick={() => void evidence("citation", index)}
              >
                Read original source {index + 1}
              </button>
            </div>
          ))}
          {detail.latest_check && (
            <>
              <h4>Saved check findings</h4>
              <ul>
                {detail.latest_check.report.errors.map((error, i) => (
                  <li key={i}>{status(error)}</li>
                ))}
              </ul>
              <button
                className="quiet-button"
                disabled={busy || !enabled}
                onClick={() => void evidence("policy", 0)}
              >
                Read policy evidence
              </button>
              {detail.latest_check.report.rubric.map((_, index) => (
                <button
                  key={index}
                  className="quiet-button"
                  disabled={busy || !enabled}
                  onClick={() => void evidence("rubric", index)}
                >
                  Read requirement {index + 1}
                </button>
              ))}
              <p>{detail.latest_check.report.limits}</p>
            </>
          )}
          <p className="subtle">{detail.limits}</p>
        </article>
      )}
      {original && (
        <section className="academic-detail" aria-label="Original document evidence">
          <h3>Original evidence</h3>
          <p>
            {original.quote_matches
              ? "Saved quotation matches this original."
              : "Quotation could not be verified."}{" "}
            Evidence: {status(original.evidence_status.state)}.
          </p>
          <blockquote>{original.reference.quote}</blockquote>
          {original.source.kind === "legacy" ? (
            <pre>{original.source.content}</pre>
          ) : (
            original.source.sections?.map((section) => (
              <div key={section.slot}>
                <h4>
                  {section.page === null ? `Section ${section.slot + 1}` : `Page ${section.page}`}
                </h4>
                <pre>{section.text}</pre>
              </div>
            ))
          )}
          {original.source.missing?.length ? (
            <p>Content gaps: {original.source.missing.map(status).join(", ")}</p>
          ) : null}
          {original.source.next_slot != null && (
            <button
              className="quiet-button"
              disabled={busy || !enabled}
              onClick={() =>
                void evidence(original.group, original.index, original.source.next_slot!)
              }
            >
              Next original section
            </button>
          )}
        </section>
      )}
    </div>
  );
}
