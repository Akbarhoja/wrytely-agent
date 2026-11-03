"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/client";
import styles from "./artifact-actions.module.css";

type Props = { artifactId: string; enabled: boolean; onSessionExpired: () => void };
export function ArtifactActions(props: Props) {
  return <Actions key={props.artifactId} {...props} />;
}
function Actions({ artifactId, enabled, onSessionExpired }: Props) {
  const [instructions, setInstructions] = useState("");
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null),
    [expired, setExpired] = useState(false);
  const controller = useRef<AbortController | null>(null),
    active = useRef(false);
  const revision = useRef<{ instructions: string; key: string } | null>(null);
  const available = enabled && !expired;
  useEffect(() => {
    if (!enabled) {
      controller.current?.abort();
      active.current = false;
      setInstructions("");
      setMessage("");
      setError(null);
    }
    return () => {
      controller.current?.abort();
      active.current = false;
    };
  }, [enabled]);
  async function run(work: (signal: AbortSignal) => Promise<void>) {
    if (!available || active.current) return;
    active.current = true;
    const request = new AbortController();
    controller.current = request;
    setBusy(true);
    setError(null);
    setMessage("");
    try {
      await work(request.signal);
    } catch (e) {
      if (!request.signal.aborted) {
        setError(
          e instanceof ApiError && e.status === 409
            ? "The draft or source access changed. Reopen the result before continuing."
            : "Could not complete this request. Check the saved result before trying again.",
        );
        if (e instanceof ApiError && e.status === 401) {
          setInstructions("");
          setExpired(true);
          onSessionExpired();
        }
      }
    } finally {
      if (!request.signal.aborted) {
        setBusy(false);
        active.current = false;
      }
    }
  }
  async function download(signal: AbortSignal) {
    const response = await fetch(`/api/agent/v2/artifacts/${artifactId}/file`, {
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
      signal,
    });
    if (!response.ok) throw new ApiError(response.status, "File unavailable");
    if (
      response.headers.get("content-type") !==
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
      throw Error();
    const blob = await response.blob();
    if (signal.aborted) return;
    const url = URL.createObjectURL(blob);
    try {
      const link = document.createElement("a");
      link.href = url;
      link.download = `wrytely-${artifactId}.docx`;
      document.body.append(link);
      link.click();
      link.remove();
      setMessage("Word download prepared. Review the draft and its disclosure before use.");
    } finally {
      setTimeout(() => URL.revokeObjectURL(url), 0);
    }
  }
  async function revise(signal: AbortSignal) {
    const text = instructions.trim();
    if (!revision.current || revision.current.instructions !== text)
      revision.current = { instructions: text, key: crypto.randomUUID() };
    const result = await api<{ task_id: string }>(`v2/artifacts/${artifactId}/revisions`, {
      method: "POST",
      signal,
      body: JSON.stringify({ instructions: text, request_key: revision.current.key }),
    });
    if (!result.task_id) throw Error();
    if (!signal.aborted)
      setMessage(
        "Revision requested. Refresh document drafts after processing to see the new version. Your previous draft is preserved.",
      );
  }
  return (
    <section className={styles.actions} aria-label="Private draft actions">
      <button
        className="quiet-button"
        disabled={!available || busy}
        onClick={() => void run(download)}
      >
        Download Word file
      </button>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (instructions.trim()) void run(revise);
        }}
      >
        <label>
          Revision instructions
          <textarea
            value={instructions}
            maxLength={4000}
            disabled={!available || busy}
            onChange={(e) => setInstructions(e.target.value)}
          />
        </label>
        <button
          className="quiet-button"
          type="submit"
          disabled={!available || busy || !instructions.trim()}
        >
          Request a revision
        </button>
      </form>
      {busy && <p role="status">Processing private draft request…</p>}
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
