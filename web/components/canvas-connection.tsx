"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/client";

type Connection = { connection_id: string; origin: string; state: string; generation: number };
type Course = {
  course_id: string;
  title: string | null;
  selected: boolean;
  missing_pending_confirmation: boolean;
  resources: {
    kind: string;
    coverage: string;
    reason: string | null;
    items_seen: number;
    retained_items: number;
    incomplete_items: number;
  }[];
};
type Coverage = {
  connection: Connection;
  scope: { mode: string; resource_kinds: string[]; course_ids: string[] };
  discovery: { coverage: string; last_attempt_at: string | null; last_complete_at: string | null };
  scan: { state: string; started_at: string | null };
  courses: Course[];
  next: string | null;
  evaluated_at: string;
};
const kinds = [
  "assignments",
  "syllabus",
  "pages",
  "announcements",
  "discussions",
  "modules",
  "submissions",
  "grades",
  "files",
];
const label = (value: string) => value.replaceAll("_", " ");
const when = (value: string | null) => (value ? new Date(value).toLocaleString() : "Not yet");

export function CanvasConnection({
  userId,
  enabled = true,
  onSessionExpired,
}: {
  userId?: string;
  enabled?: boolean;
  onSessionExpired?: () => void;
}) {
  if (!userId)
    return (
      <section className="connections-panel">
        <h2>Canvas</h2>
        <p>Sign in to connect your courses.</p>
      </section>
    );
  return <CanvasSession key={userId} enabled={enabled} onSessionExpired={onSessionExpired} />;
}
function CanvasSession({
  enabled,
  onSessionExpired,
}: {
  enabled: boolean;
  onSessionExpired?: () => void;
}) {
  const [origins, setOrigins] = useState<string[]>([]),
    [origin, setOrigin] = useState("");
  const [connections, setConnections] = useState<Connection[]>([]),
    [nextConnection, setNextConnection] = useState<string | null>(null);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [selectedCourses, setSelectedCourses] = useState<string[]>([]),
    [selectedKinds, setSelectedKinds] = useState<string[]>([]);
  const [challenge, setChallenge] = useState<{ code: string; expires_at: string } | null>(null);
  const [now, setNow] = useState(Date.now()),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<string | null>(null),
    [loaded, setLoaded] = useState(false);
  const request = useRef<AbortController | null>(null),
    active = useRef(false),
    mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      request.current?.abort();
    };
  }, []);
  useEffect(() => {
    if (!challenge) return;
    setNow(Date.now());
    const timer = setInterval(() => {
      const time = Date.now();
      setNow(time);
      if (time >= Date.parse(challenge.expires_at)) clearInterval(timer);
    }, 1000);
    return () => clearInterval(timer);
  }, [challenge]);
  useEffect(() => {
    if (!enabled) {
      request.current?.abort();
      setChallenge(null);
      setCoverage(null);
    }
  }, [enabled]);
  async function act(work: (signal: AbortSignal) => Promise<void>) {
    if (!enabled || (active.current && !request.current?.signal.aborted)) return;
    active.current = true;
    setBusy(true);
    setError(null);
    const control = new AbortController();
    request.current = control;
    try {
      await work(control.signal);
    } catch (e) {
      if (!control.signal.aborted && mounted.current) {
        setChallenge(null);
        setCoverage(null);
        setError(
          e instanceof ApiError && e.status === 404
            ? "Canvas connection setup is not installed on this workspace yet."
            : e instanceof ApiError
              ? e.message
              : "Could not load Canvas. Check your connection and try again.",
        );
        if (e instanceof ApiError && e.status === 401) {
          setConnections([]);
          onSessionExpired?.();
        }
      }
    } finally {
      if (request.current === control) {
        active.current = false;
        if (mounted.current) setBusy(false);
      }
    }
  }
  async function load(signal: AbortSignal, cursor?: string) {
    const [setup, list] = await Promise.all([
      api<{ origins: string[] }>("source-connections/canvas/setup", { signal }),
      api<{ connections: Connection[]; next_cursor: string | null }>(
        `source-connections${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
        { signal },
      ),
    ]);
    if (signal.aborted) return;
    setOrigins(setup.origins);
    setOrigin((current) => (setup.origins.includes(current) ? current : (setup.origins[0] ?? "")));
    setConnections((current) => (cursor ? [...current, ...list.connections] : list.connections));
    setNextConnection(list.next_cursor);
    setLoaded(true);
  }
  useEffect(() => {
    if (enabled) void act((signal) => load(signal));
    else setLoaded(false); /* session component is keyed by verified account */
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);
  async function inspect(signal: AbortSignal, connection: Connection, after?: string) {
    const result = await api<Coverage>(
      `source-connections/${connection.connection_id}/canvas/coverage${after ? `?after=${encodeURIComponent(after)}` : ""}`,
      { signal },
    );
    if (!signal.aborted && !after) {
      setSelectedCourses(
        result.scope.course_ids ?? result.courses.filter((c) => c.selected).map((c) => c.course_id),
      );
      setSelectedKinds(result.scope.resource_kinds);
    }
    if (!signal.aborted)
      setCoverage((previous) =>
        after && previous?.connection.connection_id === connection.connection_id
          ? { ...result, courses: [...previous.courses, ...result.courses] }
          : result,
      );
  }
  const usableChallenge =
    challenge && new Date(challenge.expires_at).getTime() > now ? challenge : null;
  return (
    <section className="connections-panel canvas-panel" aria-busy={busy}>
      <div className="section-heading">
        <h2>Canvas</h2>
        <span>Read your semester</span>
      </div>
      <p className="body-copy">
        Connect the Canvas account you use in Chrome. Wrytely discovers your courses and reads the
        content you choose while Chrome is running and Canvas is signed in.
      </p>
      <p className="privacy-note">
        Closing your laptop pauses course collection. The agent can use saved information, but
        cannot see changes until the next sync.
      </p>
      {error && (
        <p role="alert" className="connection-error">
          {error}
        </p>
      )}
      <button
        className="quiet-button"
        disabled={busy || !enabled}
        onClick={() => void act((signal) => load(signal))}
      >
        {busy ? "Working…" : "Refresh connections"}
      </button>
      {loaded && origins.length === 0 && (
        <p>Canvas setup is not available on this workspace yet.</p>
      )}
      {origins.length > 0 && (
        <div className="canvas-link-form">
          <label htmlFor="canvas-origin">Your university Canvas</label>
          <select
            id="canvas-origin"
            value={origin}
            disabled={busy || !enabled}
            onChange={(e) => {
              setOrigin(e.target.value);
              setChallenge(null);
            }}
          >
            {origins.map((value) => (
              <option key={value} value={value}>
                {new URL(value).hostname}
              </option>
            ))}
          </select>
          <p>
            Install the Wrytely Canvas extension supplied for this workspace, then create a private
            linking code and enter it in the extension. Your Canvas password stays with Canvas.
          </p>
          <button
            className="primary-button"
            disabled={busy || !enabled || !origin}
            onClick={() =>
              void act(async (signal) => {
                const result = await api<{ code: string; expires_at: string }>(
                  "source-connections/canvas/pairing",
                  { method: "POST", body: JSON.stringify({ origin }), signal },
                );
                if (!signal.aborted) setChallenge(result);
              })
            }
          >
            Create linking code
          </button>
          {usableChallenge && (
            <div className="canvas-code" role="status">
              <p>Enter this code in the extension before {when(usableChallenge.expires_at)}.</p>
              <code>{usableChallenge.code}</code>
              <button
                className="quiet-button"
                disabled={busy}
                onClick={() =>
                  void act(async () => {
                    await navigator.clipboard.writeText(usableChallenge.code);
                  })
                }
              >
                Copy code
              </button>
              <p>After linking, refresh connections here. Do not share this code.</p>
            </div>
          )}
          {challenge && !usableChallenge && (
            <p role="status">Linking code expired. Create a new code.</p>
          )}
        </div>
      )}
      {connections.map((connection) => (
        <div className="canvas-account" key={connection.connection_id}>
          <h3>{new URL(connection.origin).hostname}</h3>
          <p>Status: {label(connection.state)}</p>
          <div className="canvas-actions">
            <button
              className="quiet-button"
              disabled={busy || !enabled}
              onClick={() => void act((signal) => inspect(signal, connection))}
            >
              View courses and coverage
            </button>
            {connection.state === "connected" && (
              <button
                className="quiet-button"
                disabled={busy || !enabled}
                onClick={() =>
                  void act(async (signal) => {
                    await api("source-connections/canvas/scope", {
                      method: "POST",
                      signal,
                      body: JSON.stringify({
                        connection_id: connection.connection_id,
                        generation: connection.generation,
                        mode: "all_active",
                        course_ids: [],
                        resource_kinds: kinds,
                      }),
                    });
                    if (!signal.aborted) {
                      setCoverage(null);
                      await load(signal);
                      await inspect(signal, connection);
                    }
                  })
                }
              >
                Read all active courses
              </button>
            )}
            {connection.state !== "disconnected" && (
              <button
                className="quiet-button"
                disabled={busy || !enabled}
                onClick={() =>
                  void act(async (signal) => {
                    setChallenge(null);
                    setCoverage(null);
                    await api(`source-connections/${connection.connection_id}/revoke`, {
                      method: "POST",
                      body: "{}",
                      signal,
                    });
                    await load(signal);
                  })
                }
              >
                Disconnect Canvas
              </button>
            )}
          </div>
          {connection.state === "connected" && (
            <p>
              “Read all active courses” includes future active courses, syllabus, assignments,
              rubrics, announcements, discussions, modules, pages, your submissions, grades and
              readable files. Hidden or external content remains a gap. It never starts or submits a
              quiz.
            </p>
          )}
          {connection.state === "reconnect_required" && (
            <p>Create a new linking code above and reconnect the extension.</p>
          )}
        </div>
      ))}
      {nextConnection && (
        <button
          className="quiet-button"
          disabled={busy || !enabled}
          onClick={() => void act((signal) => load(signal, nextConnection))}
        >
          More connections
        </button>
      )}
      {coverage && (
        <div className="canvas-coverage" aria-live="polite">
          <h3>Your courses</h3>
          <p>
            Scope: {label(coverage.scope.mode)} · Latest scan: {label(coverage.scan.state)} ·
            Started: {when(coverage.scan.started_at)}
          </p>
          <p>
            Discovery: {label(coverage.discovery.coverage)}. Last attempt:{" "}
            {when(coverage.discovery.last_attempt_at)}. Last complete course discovery:{" "}
            {when(coverage.discovery.last_complete_at)}.
          </p>
          <p>
            A finished scan can still have missing content. These are saved observations, not a
            promise that Canvas has not changed. PDF text can omit images, and restricted or
            external content cannot be read.
          </p>
          {coverage.courses.length === 0 && (
            <p>
              No courses discovered yet. Keep Chrome running and Canvas signed in, then use Sync in
              the extension.
            </p>
          )}
          {coverage.connection.state === "connected" && (
            <details className="canvas-scope">
              <summary>Choose specific courses and content</summary>
              <p>
                Save a specific selection to stop automatically including new courses. Changes
                cancel the current scan; sync again afterward.
              </p>
              <fieldset disabled={busy || !enabled}>
                <legend>Courses discovered so far</legend>
                {coverage.courses.map((course) => (
                  <label key={course.course_id}>
                    <input
                      type="checkbox"
                      checked={selectedCourses.includes(course.course_id)}
                      onChange={(e) =>
                        setSelectedCourses((current) =>
                          e.target.checked
                            ? [...current, course.course_id]
                            : current.filter((id) => id !== course.course_id),
                        )
                      }
                    />
                    {course.title || `Course ${course.course_id}`}
                  </label>
                ))}
              </fieldset>
              <fieldset disabled={busy || !enabled}>
                <legend>Content to read</legend>
                {kinds.map((kind) => (
                  <label key={kind}>
                    <input
                      type="checkbox"
                      checked={selectedKinds.includes(kind)}
                      onChange={(e) =>
                        setSelectedKinds((current) =>
                          e.target.checked
                            ? [...current, kind]
                            : current.filter((value) => value !== kind),
                        )
                      }
                    />
                    {label(kind)}
                  </label>
                ))}
              </fieldset>
              <button
                className="quiet-button"
                disabled={busy || !enabled}
                onClick={() =>
                  void act(async (signal) => {
                    await api("source-connections/canvas/scope", {
                      method: "POST",
                      signal,
                      body: JSON.stringify({
                        connection_id: coverage.connection.connection_id,
                        generation: coverage.connection.generation,
                        mode: "explicit_set",
                        course_ids: selectedCourses,
                        resource_kinds: selectedKinds,
                      }),
                    });
                    if (!signal.aborted) await inspect(signal, coverage.connection);
                  })
                }
              >
                Save selected courses and content
              </button>
            </details>
          )}
          {coverage.courses.map((course) => (
            <details key={course.course_id} className="canvas-course">
              <summary>
                {course.title || `Course ${course.course_id}`} ·{" "}
                {course.selected ? "Selected" : "Not selected"}
                {course.missing_pending_confirmation ? " · Availability needs confirmation" : ""}
              </summary>
              <ul>
                {course.resources.map((resource) => (
                  <li key={resource.kind}>
                    <strong>{label(resource.kind)}</strong>: {label(resource.coverage)};{" "}
                    {resource.items_seen} seen this scan, {resource.retained_items} retained,{" "}
                    {resource.incomplete_items} with content gaps
                    {resource.reason ? ` · ${label(resource.reason)}` : ""}
                  </li>
                ))}
              </ul>
            </details>
          ))}
          {coverage.next && (
            <button
              className="quiet-button"
              disabled={busy || !enabled}
              onClick={() =>
                void act((signal) => inspect(signal, coverage.connection, coverage.next!))
              }
            >
              More courses
            </button>
          )}
        </div>
      )}
      <div className="canvas-optional">
        <h3>Outlook email · Optional</h3>
        <p>
          Not connected. University approval may be required. Email is optional and does not block
          Canvas. Outlook connection setup is paused in this version.
        </p>
      </div>
    </section>
  );
}
