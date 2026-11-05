"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/client";
import styles from "./course-supervision.module.css";
import { supervisionReason } from "../lib/supervision-reason";
import { CoursePreparations } from "./course-preparations";
import { parsePreparations, type Preparation } from "../lib/preparations";

type Monitor = {
  id: string;
  state: string;
  next_check_at: string | null;
  calls_reserved: number;
  call_limit: number;
  notification_consent: boolean;
  reason: string | null;
  offers: { id: string; message: string; reason: string; state: string }[];
  preparations?: Preparation[];
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function CourseSupervision(props: {
  userId: string;
  connectionId: string;
  courseId: string;
  title: string;
  enabled: boolean;
  selected: boolean;
  onSessionExpired?: () => void;
  onViewResults?: () => void;
}) {
  return <Session key={`${props.userId}:${props.connectionId}:${props.courseId}`} {...props} />;
}

function Session({
  userId,
  connectionId,
  courseId,
  title,
  enabled,
  selected,
  onSessionExpired,
  onViewResults,
}: Parameters<typeof CourseSupervision>[0]) {
  const key = `wrytely:course-supervision:${userId}:${connectionId}:${courseId}`;
  const [monitor, setMonitor] = useState<Monitor | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false),
    [notice, setNotice] = useState("");
  const control = useRef<AbortController | null>(null),
    active = useRef(false);
  const available = enabled && !expired;

  async function read(id: string, signal: AbortSignal) {
    const value = await api<Monitor>(`course-supervisions/${id}`, { signal });
    if (
      value.id !== id ||
      !uuid.test(value.id) ||
      typeof value.state !== "string" ||
      !Number.isSafeInteger(value.calls_reserved) ||
      !Number.isSafeInteger(value.call_limit) ||
      !Array.isArray(value.offers) ||
      value.offers.some(
        (x) =>
          !uuid.test(x.id) || [x.state, x.message, x.reason].some((y) => typeof y !== "string"),
      ) ||
      typeof value.notification_consent !== "boolean"
    )
      throw Error();
    const preparations = parsePreparations(value.preparations);
    if (!signal.aborted) setMonitor({ ...value, preparations });
  }
  async function run(work: (signal: AbortSignal) => Promise<void>) {
    if (!available || active.current) return;
    const request = new AbortController();
    control.current = request;
    active.current = true;
    setBusy(true);
    setError(null);
    setNotice("");
    // A failed refresh cannot leave old checklists claiming current evidence.
    setMonitor((previous) => (previous ? { ...previous, preparations: [] } : previous));
    try {
      await work(request.signal);
    } catch (e) {
      if (!request.signal.aborted) {
        setError(
          e instanceof ApiError && e.status === 409
            ? "Course access changed. Sync Canvas and refresh supervision."
            : "Could not update supervision. Refresh to check its saved state.",
        );
        if (e instanceof ApiError && e.status === 401) {
          setMonitor(null);
          setExpired(true);
          onSessionExpired?.();
        }
      }
    } finally {
      if (!request.signal.aborted) {
        setBusy(false);
        active.current = false;
      }
    }
  }
  useEffect(() => {
    if (enabled) {
      void run(async (signal) => {
        const query = new URLSearchParams({ connection_id: connectionId, course_id: courseId });
        const value = await api<{ supervision: Monitor | null }>(`course-supervisions?${query}`, {
          signal,
        });
        if (signal.aborted) return;
        if (value.supervision) {
          if (!uuid.test(value.supervision.id)) throw Error();
          await read(value.supervision.id, signal);
        } else if (!signal.aborted) setMonitor(null);
      });
    } else {
      control.current?.abort();
      active.current = false;
      setMonitor(null);
      setNotice("");
      setBusy(false);
    }
    return () => {
      control.current?.abort();
      active.current = false;
    };
  }, [enabled, key]);

  async function enable(signal: AbortSignal) {
    const value = await api<Monitor>("course-supervisions", {
      method: "POST",
      signal,
      body: JSON.stringify({ connection_id: connectionId, course_id: courseId }),
    });
    if (!uuid.test(value.id)) throw Error();
    if (!signal.aborted) {
      await read(value.id, signal);
    }
  }
  async function action(path: string, signal: AbortSignal, body?: object) {
    const result = await api<{ responsibility_id?: string }>(path, {
      method: "POST",
      signal,
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    if (!signal.aborted && monitor) {
      await read(monitor.id, signal);
      if (!signal.aborted && result.responsibility_id)
        setNotice("Draft requested. Open Private results to follow its progress.");
    }
  }
  const root = monitor ? `course-supervisions/${monitor.id}` : "";
  return (
    <section className={styles.panel} aria-label={`Supervision for ${title}`} aria-busy={busy}>
      <h4>Course supervision</h4>
      <p>
        Wrytely can review saved course evidence and offer help. You decide whether to start a
        draft. Canvas updates require a connected browser.
      </p>
      {!monitor && (
        <>
          <button
            className="quiet-button"
            disabled={!available || busy || !selected}
            onClick={() => void run(enable)}
          >
            Enable supervision
          </button>
          {!selected && <p>Select this course and its content before enabling supervision.</p>}
        </>
      )}
      {monitor && (
        <>
          <p>
            Status: {monitor.state.replaceAll("_", " ")}. Next check:{" "}
            {monitor.next_check_at
              ? new Date(monitor.next_check_at).toLocaleString()
              : "Not scheduled"}
            .
          </p>
          <p className={styles.usage}>
            {monitor.calls_reserved} of {monitor.call_limit} checks reserved. Checks use saved
            evidence and depend on service availability.
          </p>
          {monitor.reason && (
            <p role="status">
              {supervisionReason(monitor.reason)} No automatic retry was started. Refresh only
              checks the saved state.
            </p>
          )}
          <div className={styles.controls}>
            <button
              className="quiet-button"
              disabled={!available || busy}
              onClick={() => void run((signal) => read(monitor.id, signal))}
            >
              Refresh supervision
            </button>
            <button
              className="quiet-button"
              disabled={!available || busy || monitor.state === "paused"}
              onClick={() => void run((signal) => action(`${root}/pause`, signal))}
            >
              Pause supervision
            </button>
          </div>
          <label>
            <input
              type="checkbox"
              checked={monitor.notification_consent}
              disabled={!available || busy}
              onChange={(e) => {
                const consent = e.currentTarget.checked;
                void run((signal) => action(`${root}/notifications`, signal, { consent }));
              }}
            />{" "}
            Allow WhatsApp offers for this course
          </label>
          <p className={styles.notice}>
            Requires a linked phone and working WhatsApp account. Reading a course or accepting a
            draft does not enable notifications.
          </p>
          {monitor.offers.length === 0 && <p>No offers yet. Refresh after a supervision check.</p>}
          {monitor.offers.map((offer) => (
            <article key={offer.id} className={styles.offer}>
              <p>
                <strong>{offer.message}</strong>
              </p>
              <p>{offer.reason}</p>
              <p>{offer.state.replaceAll("_", " ")}</p>
              {offer.state === "pending" && (
                <div className={styles.controls}>
                  <button
                    className="quiet-button"
                    disabled={!available || busy || monitor.state === "paused"}
                    onClick={() =>
                      void run((signal) =>
                        action(`${root}/offers/${offer.id}/decision`, signal, { accept: true }),
                      )
                    }
                  >
                    Accept and prepare draft
                  </button>
                  <button
                    className="quiet-button"
                    disabled={!available || busy || monitor.state === "paused"}
                    onClick={() =>
                      void run((signal) =>
                        action(`${root}/offers/${offer.id}/decision`, signal, { accept: false }),
                      )
                    }
                  >
                    Decline offer
                  </button>
                </div>
              )}
            </article>
          ))}
          <p className={styles.notice}>
            On WhatsApp, reply to an offer with /accept or /decline. After the draft is ready, reply
            /file for the checked file, or /revise followed by your changes.
          </p>
          {!busy && <CoursePreparations records={monitor.preparations ?? []} />}
        </>
      )}
      {busy && <p role="status">Saving or refreshing supervision…</p>}
      {error && <p role="alert">{error}</p>}
      {notice && (
        <p role="status">
          {notice}{" "}
          {onViewResults && (
            <button className="quiet-button" onClick={onViewResults}>
              Open Private results
            </button>
          )}
        </p>
      )}
    </section>
  );
}
