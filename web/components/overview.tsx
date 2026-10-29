"use client";

import {
  ArrowUpRight,
  ArrowsClockwise,
  BookOpen,
  Check,
  CircleNotch,
  Flag,
  Lightning,
  Pause,
  Tray,
} from "@phosphor-icons/react";
import type { WorkItem } from "@/lib/client";

type Props = {
  work: WorkItem[];
  loaded: boolean;
  loading: boolean;
  signedIn: boolean;
  paused: boolean;
  configured: boolean;
  error: boolean;
  onConversation: () => void;
  onConnections: () => void;
  onRefresh: () => void;
};
const groups = [
  {
    key: "active",
    label: "In motion",
    icon: Lightning,
    empty: "Nothing in motion yet.",
    detail: "Work Wrytely picks up will appear here.",
  },
  {
    key: "blocked",
    label: "Needs attention",
    icon: Flag,
    empty: "No blocked work.",
    detail: "When something gets stuck, you’ll see it here.",
  },
  {
    key: "done",
    label: "Completed",
    icon: Check,
    empty: "A little progress starts here.",
    detail: "Finished work will stay here for you to revisit.",
  },
] as const;
const labels = { ready: "Queued", running: "Working", blocked: "Blocked", done: "Completed" };

export function Overview({
  work,
  loaded,
  loading,
  signedIn,
  paused,
  configured,
  error,
  onConversation,
  onConnections,
  onRefresh,
}: Props) {
  const known = signedIn && loaded;
  const activeCount = work.filter((item) => ["ready", "running"].includes(item.status)).length;
  const doneCount = work.filter((item) => item.status === "done").length;
  const blockedCount = work.filter((item) => item.status === "blocked").length;
  const status = loading
    ? "Loading your workspace"
    : error
      ? "Connection needs attention"
      : paused
        ? "Your agent is paused"
        : known
          ? "Your workspace is connected"
          : "Your agent starts here";
  return (
    <div className="overview-layout">
      <div className="overview-main">
        <section className="agent-brief" aria-labelledby="agent-brief-title">
          <div className="brief-top">
            <span className="brief-mark">w</span>
            <span>Wrytely · Your academic agent</span>
          </div>
          <h2 id="agent-brief-title">
            {known
              ? paused
                ? "Your work is saved. Take a breather."
                : activeCount
                  ? `${activeCount} ${activeCount === 1 ? "task" : "tasks"} moving forward.`
                  : "Your latest work, all in one place."
              : "More room for being a student."}
          </h2>
          <p>
            {known
              ? `${error ? "Last loaded: " : ""}${activeCount} in motion. ${doneCount} completed. ${blockedCount} needing attention. ${work.length ? "See the recent work below." : "Talk with Wrytely to get started."}`
              : "Your assignments, team work and follow-through, brought into one place. See what’s moving. Step in when you’re needed."}
          </p>
          <div className="brief-bottom">
            <span>
              {loading ? (
                <CircleNotch className="spinner" size={17} aria-hidden />
              ) : paused ? (
                <Pause size={17} aria-hidden />
              ) : (
                <span className="brief-status-dot" aria-hidden />
              )}
              {status}
            </span>
            {signedIn ? (
              <button onClick={onConversation}>
                Talk to Wrytely <ArrowUpRight size={16} aria-hidden />
              </button>
            ) : configured ? (
              <a href="/sign-up">
                Set up your agent <ArrowUpRight size={16} aria-hidden />
              </a>
            ) : (
              <span className="brief-setup">Sign-in is being connected</span>
            )}
          </div>
        </section>

        <div className="work-heading">
          <div>
            <h2>What Wrytely is handling</h2>
            <p>
              {paused
                ? "Work stays saved while paused."
                : "Your most recent work, from first step to follow-through."}
            </p>
          </div>
          {signedIn && (
            <button
              className="refresh-work"
              onClick={onRefresh}
              disabled={loading}
              aria-label="Refresh work"
            >
              <ArrowsClockwise size={18} aria-hidden />
            </button>
          )}
        </div>
        <div className="work-board">
          {groups.map(({ key, label, icon: Icon, empty, detail }) => {
            const items = work.filter((item) =>
              key === "active" ? ["ready", "running"].includes(item.status) : item.status === key,
            );
            return (
              <section className={`work-lane lane-${key}`} aria-label={label} key={key}>
                <header>
                  <Icon size={18} aria-hidden />
                  <h3>{label}</h3>
                  <span aria-label={known ? `${items.length} recent tasks` : "Not loaded"}>
                    {known ? items.length : "—"}
                  </span>
                </header>
                {known && items.length ? (
                  <ul className="work-items">
                    {items.map((item) => (
                      <li key={item.id}>
                        <span className="work-source">
                          <BookOpen size={13} aria-hidden />
                          Conversation task
                        </span>
                        <h4>{item.title}</h4>
                        <div className="work-item-bottom">
                          <span className={`work-status status-${item.status}`}>
                            {paused && ["ready", "running"].includes(item.status)
                              ? "Paused"
                              : labels[item.status]}
                          </span>
                          <button
                            onClick={onConversation}
                            aria-label={`Open conversation for ${item.title}`}
                          >
                            <ArrowUpRight size={16} aria-hidden />
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="lane-empty">
                    <span className="lane-empty-mark">
                      <Icon size={22} aria-hidden />
                    </span>
                    <h4>
                      {loading
                        ? "Loading saved work…"
                        : error && !known
                          ? "Work is unavailable."
                          : known
                            ? empty
                            : "Your work will appear here."}
                    </h4>
                    <p>{known ? detail : "Connect your account to see your agent’s work."}</p>
                  </div>
                )}
              </section>
            );
          })}
        </div>
        <p className="work-scope">
          {known
            ? "Showing up to 50 recent tasks. Course workflows are not connected yet."
            : "No sample assignments or activity. This space will show your own work."}
        </p>
      </div>

      <aside className="overview-rail" aria-label="Your decisions and connections">
        <section className="decisions-panel">
          <div className="section-heading">
            <h2>Your decisions</h2>
            <Flag size={18} aria-hidden />
          </div>
          <div className="decision-empty">
            <Tray size={27} aria-hidden />
            <h3>Space for your say.</h3>
            <p>
              When Wrytely needs your choice, the request will appear here with the context you
              need.
            </p>
            <span>Decision requests are not connected yet</span>
          </div>
        </section>
        <section className="semester-panel">
          <BookOpen size={24} aria-hidden />
          <h2>Bring your semester together.</h2>
          <p>Canvas for your courses. Teams for your people. One agent to help connect the dots.</p>
          <div className="integration-names">
            <span>Canvas</span>
            <span>Teams</span>
            <span>Calendar</span>
          </div>
          <button className="text-button" onClick={onConnections}>
            See connections <ArrowUpRight size={16} aria-hidden />
          </button>
          <p className="connection-footnote">Connections are coming soon.</p>
        </section>
        <p className="rail-footnote">
          Your agent should carry the work forward. You shouldn’t have to manage every step.
        </p>
      </aside>
    </div>
  );
}
