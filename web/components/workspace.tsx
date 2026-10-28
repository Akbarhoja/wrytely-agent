"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import {
  ArrowUp,
  ArrowUpRight,
  BookOpen,
  CalendarBlank,
  ChatCircle,
  Check,
  CircleNotch,
  LinkSimple,
  Pause,
  Play,
  Sparkle,
  Tray,
  WarningCircle,
  SquaresFour,
} from "@phosphor-icons/react";
import { useWorkspace } from "@/lib/use-workspace";
import { Overview } from "./overview";
import { WhatsAppConnection } from "./whatsapp-connection";

type Props = {
  mode: "signed-in" | "signed-out" | "unconfigured" | "loading";
  userId?: string;
  name?: string;
  account?: ReactNode;
};
const starters = [
  "Help me understand an assignment",
  "Break a big task into smaller steps",
  "Help me plan my study time",
];

export function Workspace({ mode, userId, name, account }: Props) {
  const data = useWorkspace(userId);
  const [view, setView] = useState<"overview" | "conversation" | "connections">("overview");
  const signedIn = mode === "signed-in";
  const working = data.task && ["ready", "running"].includes(data.task.status);
  const state =
    mode === "loading" || data.loading
      ? "Getting ready"
      : data.agent?.paused
        ? "Paused"
        : working
          ? data.task?.status === "running"
            ? "Working on your message"
            : "Message queued"
          : data.agent
            ? "Ready for your message"
            : "Your academic agent";
  const ready = signedIn && Boolean(data.agent) && !data.loading && !data.expired;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace">
        Skip to workspace
      </a>
      <aside className="sidebar">
        <Link href="/" className="brand" aria-label="Wrytely home">
          wrytely
          <ArrowUpRight weight="bold" aria-hidden />
        </Link>
        <div className="sidebar-body">
          <p className="sidebar-caption">YOUR SPACE</p>
          <nav aria-label="Workspace">
            <button
              className={view === "overview" ? "nav-item selected" : "nav-item"}
              onClick={() => setView("overview")}
              aria-current={view === "overview" ? "page" : undefined}
            >
              <SquaresFour size={20} aria-hidden />
              Overview
            </button>
            <button
              className={view === "conversation" ? "nav-item selected" : "nav-item"}
              onClick={() => setView("conversation")}
              aria-current={view === "conversation" ? "page" : undefined}
            >
              <ChatCircle size={20} aria-hidden />
              Conversation
            </button>
            <button
              className={view === "connections" ? "nav-item selected" : "nav-item"}
              onClick={() => setView("connections")}
              aria-current={view === "connections" ? "page" : undefined}
            >
              <LinkSimple size={20} aria-hidden />
              Connections
            </button>
          </nav>
          <div className="sidebar-note">
            <BookOpen size={24} aria-hidden />
            <p>A little less to carry.</p>
            <span>Your semester has a lot of moving parts. Let’s bring them together.</span>
          </div>
        </div>
        <div className="profile">
          {account || (
            <div className="profile-symbol">
              <Sparkle size={19} aria-hidden />
            </div>
          )}
          <div>
            <strong>{signedIn ? name : "Your space, your pace"}</strong>
            <span>{signedIn ? "Personal workspace" : "Built around you"}</span>
          </div>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <span>
            Workspace <span className="crumb">/</span>{" "}
            <strong>
              {view === "overview"
                ? "Overview"
                : view === "conversation"
                  ? "Conversation"
                  : "Connections"}
            </strong>
          </span>
          <div className="topbar-actions">
            {signedIn && data.agent ? (
              <button
                className="quiet-button"
                disabled={data.changing || data.expired}
                onClick={() => void data.togglePause()}
                aria-pressed={data.agent.paused}
              >
                {data.agent.paused ? (
                  <Play size={16} aria-hidden />
                ) : (
                  <Pause size={16} aria-hidden />
                )}
                {data.changing ? "Updating…" : data.agent.paused ? "Resume agent" : "Pause agent"}
              </button>
            ) : mode === "signed-out" ? (
              <Link className="quiet-button" href="/sign-in">
                Sign in <ArrowUpRight size={16} aria-hidden />
              </Link>
            ) : (
              <span className="subtle">Made for your semester</span>
            )}
          </div>
        </header>

        <main id="workspace" className="workspace" tabIndex={-1}>
          <section className="intro">
            <div className="agent-label">
              <span className={`status-dot ${data.agent?.paused ? "paused" : ""}`} aria-hidden />
              {state}
            </div>
            <h1>
              {view === "overview"
                ? signedIn
                  ? `Your semester, moving forward, ${name}.`
                  : "Your semester, moving forward."
                : view === "conversation"
                  ? "Talk things through with Wrytely."
                  : "Your semester, connected."}
            </h1>
            <p>
              {view === "overview"
                ? "See what’s being handled, what needs attention, and what’s already done."
                : view === "conversation"
                  ? "Give your agent context, ask a question, or talk about the next step."
                  : "Bring your courses and conversations into your agent’s world."}
            </p>
          </section>

          {data.error && (
            <div className="error-banner" role="alert">
              <WarningCircle size={20} aria-hidden />
              <span>{data.error}</span>
              {data.expired ? (
                <Link href="/sign-in">Sign in again</Link>
              ) : (
                <button onClick={data.retry}>Reconnect</button>
              )}
            </div>
          )}
          {view === "overview" ? (
            <Overview
              work={data.work}
              loaded={data.workLoaded}
              loading={data.loading || mode === "loading"}
              signedIn={signedIn}
              paused={Boolean(data.agent?.paused)}
              configured={mode === "signed-out"}
              error={Boolean(data.error)}
              onConversation={() => setView("conversation")}
              onConnections={() => setView("connections")}
              onRefresh={data.retry}
            />
          ) : view === "connections" ? (
            <div className="connections-layout">
              <WhatsAppConnection mode={mode === "signed-in" ? "unavailable" : mode} />
              <section className="connections-panel">
                <div className="section-heading">
                  <h2>Bring your semester together</h2>
                  <span>Course integrations</span>
                </div>
                <p className="body-copy">
                  Your connections will help Wrytely understand what’s happening across your
                  courses.
                </p>
                {[
                  {
                    name: "Canvas",
                    detail: "Assignments, deadlines and course discussions",
                    icon: BookOpen,
                  },
                  {
                    name: "Microsoft Teams",
                    detail: "Team conversations and shared work",
                    icon: ChatCircle,
                  },
                  {
                    name: "Calendar",
                    detail: "Classes, meetings and study time",
                    icon: CalendarBlank,
                  },
                ].map(({ name: label, detail, icon: Icon }) => (
                  <div className="connection-row" key={label}>
                    <div className="connection-icon">
                      <Icon size={23} aria-hidden />
                    </div>
                    <div>
                      <h3>{label}</h3>
                      <p>{detail}</p>
                    </div>
                    <span className="coming">Coming soon</span>
                  </div>
                ))}
                <p className="privacy-note">
                  <Check size={16} aria-hidden />
                  {signedIn
                    ? "Course connections are not available yet."
                    : "No courses or chats are connected yet."}
                </p>
              </section>
            </div>
          ) : (
            <div className="workspace-grid">
              <section className="conversation" aria-label="Conversation with Wrytely">
                <div className="conversation-heading">
                  <div className="agent-avatar">w</div>
                  <div>
                    <h2>Wrytely</h2>
                    <p>Your academic agent</p>
                  </div>
                  <span className="personal-label">Just for you</span>
                </div>
                <div
                  className="messages"
                  role="log"
                  aria-label="Messages"
                  aria-live="polite"
                  aria-relevant="additions text"
                >
                  {data.messages.length ? (
                    data.messages.map((message) => (
                      <article className={`message ${message.role}`} key={message.id}>
                        <span className="message-author">
                          {message.role === "user" ? "You" : "Wrytely"}
                        </span>
                        <p>{message.content}</p>
                      </article>
                    ))
                  ) : (
                    <div className="welcome">
                      <div className="welcome-icon">
                        <Sparkle size={28} weight="duotone" aria-hidden />
                      </div>
                      <h3>
                        {signedIn
                          ? "What’s on your mind?"
                          : "You bring the ambition.\nWe’ll help with the moving parts."}
                      </h3>
                      <p>
                        {signedIn
                          ? "Start with an assignment, a question, or something you’re finding hard to get started on."
                          : "Less switching between tabs. More space to learn, make progress, and enjoy being a student."}
                      </p>
                      {mode === "signed-out" ? (
                        <Link className="primary-button" href="/sign-up">
                          Create your workspace <ArrowUpRight size={18} aria-hidden />
                        </Link>
                      ) : mode === "unconfigured" ? (
                        <p className="setup-note">
                          We’re connecting sign-in. Your workspace will be ready here soon.
                        </p>
                      ) : mode === "loading" || data.loading ? (
                        <p className="loading-line">
                          <CircleNotch className="spinner" size={18} aria-hidden />
                          Getting your workspace ready…
                        </p>
                      ) : (
                        <div className="starters">
                          {starters.map((text) => (
                            <button
                              key={text}
                              disabled={!ready || data.uncertain || Boolean(working)}
                              onClick={() => data.edit(text)}
                            >
                              {text}
                              <ArrowUpRight size={15} aria-hidden />
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div className="conversation-bottom">
                  {data.task?.status === "blocked" && (
                    <p className="task-note" role="status">
                      Wrytely couldn’t finish that message. It’s saved in your conversation.
                    </p>
                  )}
                  {working && (
                    <p className="task-note" role="status">
                      {data.agent?.paused ? (
                        <Pause size={16} aria-hidden />
                      ) : (
                        <CircleNotch className="spinner" size={16} aria-hidden />
                      )}
                      {data.agent?.paused
                        ? "Your message is saved. Resume Wrytely to continue."
                        : data.task?.status === "running"
                          ? "Wrytely is working on your message…"
                          : "Your message is saved and waiting to run."}
                    </p>
                  )}
                  {data.uncertain && (
                    <p className="task-note">
                      The connection dropped before confirmation. Retry to safely check the same
                      message.
                    </p>
                  )}
                  <form
                    className="composer"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void data.send();
                    }}
                  >
                    <label htmlFor="message" className="sr-only">
                      Message Wrytely
                    </label>
                    <textarea
                      id="message"
                      value={data.draft}
                      onChange={(event) => data.edit(event.target.value)}
                      maxLength={12000}
                      disabled={!ready || data.sending || data.uncertain || Boolean(working)}
                      placeholder={
                        signedIn
                          ? "Tell Wrytely what’s on your mind…"
                          : "Your semester starts with a conversation…"
                      }
                      rows={2}
                    />
                    <div className="composer-footer">
                      <span>
                        {data.agent?.paused
                          ? "Paused · messages will wait"
                          : "A little context goes a long way"}
                      </span>
                      <button
                        className="send-button"
                        type="submit"
                        aria-label={data.uncertain ? "Retry this message" : "Send message"}
                        disabled={
                          !ready ||
                          data.sending ||
                          Boolean(working) ||
                          (!data.draft.trim() && !data.uncertain)
                        }
                      >
                        {data.sending ? (
                          <CircleNotch className="spinner" size={20} aria-hidden />
                        ) : data.uncertain ? (
                          "Retry"
                        ) : (
                          <ArrowUp size={20} weight="bold" aria-hidden />
                        )}
                      </button>
                    </div>
                  </form>
                  <p className="composer-note">
                    {signedIn
                      ? "Wrytely can make mistakes. Check important details."
                      : "Your conversations stay in your own workspace."}
                  </p>
                </div>
              </section>

              <aside className="right-rail" aria-label="Agent activity">
                <section className="activity-panel">
                  <div className="section-heading">
                    <h2>In the loop</h2>
                    <Tray size={19} aria-hidden />
                  </div>
                  <div className="activity-empty">
                    <div className="activity-glyph">
                      <Check size={23} aria-hidden />
                    </div>
                    <h3>
                      {data.agent?.paused
                        ? "Taking a pause."
                        : working
                          ? "One thing in motion."
                          : "Room for what’s next."}
                    </h3>
                    <p>
                      {working
                        ? "Your current message is saved. You’ll see the result in your conversation."
                        : "Work Wrytely picks up will appear here. For now, start with a conversation."}
                    </p>
                    {data.task && (
                      <span className="task-state">
                        {data.task.status === "ready"
                          ? "Queued"
                          : data.task.status === "running"
                            ? "Working"
                            : data.task.status === "done"
                              ? "Completed"
                              : "Needs attention"}
                      </span>
                    )}
                  </div>
                </section>
                <section className="sources-panel">
                  <div className="section-heading">
                    <h2>Your connections</h2>
                    <LinkSimple size={18} aria-hidden />
                  </div>
                  <div className="source-list">
                    <span>
                      <BookOpen size={18} aria-hidden />
                      Canvas<em>Coming soon</em>
                    </span>
                    <span>
                      <ChatCircle size={18} aria-hidden />
                      Teams<em>Coming soon</em>
                    </span>
                  </div>
                  <button className="text-button" onClick={() => setView("connections")}>
                    See connections <ArrowUpRight size={16} aria-hidden />
                  </button>
                </section>
                <p className="rail-footnote">
                  Built to give you more space for the part that matters: learning.
                </p>
              </aside>
            </div>
          )}
        </main>
        <footer className="page-footer">
          <span>wrytely</span>
          <span>One semester. One step at a time.</span>
        </footer>
      </div>
    </div>
  );
}
