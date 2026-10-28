"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowUpRight, Check, CircleNotch, WhatsappLogo } from "@phosphor-icons/react";

export type CommunicationPreferences = {
  consent: boolean;
  timezone: string;
  quiet_start: number;
  quiet_end: number;
};
export type ConnectionView = {
  linked: boolean;
  phoneLast4: string | null;
  destination: string | null;
  configured: boolean;
  preferences: CommunicationPreferences | null;
  delivery: { state: string; reason: string | null; retryAt?: string | null } | null;
};
export type LinkChallenge = { message: string; expiresAt: number };
type Props = {
  mode: "ready" | "signed-out" | "unconfigured" | "unavailable" | "loading" | "error" | "expired";
  connection?: ConnectionView;
  challenge?: LinkChallenge;
  busy?: string | null;
  uncertain?: boolean;
  error?: string | null;
  onLink?: () => void | Promise<void>;
  onRefresh?: () => void;
  onExpire?: () => void;
  onDisconnect?: () => Promise<boolean>;
  onSave?: (preferences: CommunicationPreferences) => Promise<boolean>;
};

export function WhatsAppConnection(props: Props) {
  const { mode, connection, challenge, busy, uncertain } = props;
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const [now, setNow] = useState(Date.now);
  const [actionPending, setActionPending] = useState<string | null>(null);
  const [actionError, setActionError] = useState(false);
  const actionLock = useRef(false);
  const disconnectButton = useRef<HTMLButtonElement>(null);
  const keepConnectionButton = useRef<HTMLButtonElement>(null);
  const restoreDisconnectFocus = useRef(false);
  const onExpire = useRef(props.onExpire);
  onExpire.current = props.onExpire;

  useEffect(() => {
    if (confirmDisconnect) {
      restoreDisconnectFocus.current = true;
      keepConnectionButton.current?.focus();
    } else if (restoreDisconnectFocus.current) {
      disconnectButton.current?.focus();
      restoreDisconnectFocus.current = false;
    }
  }, [confirmDisconnect]);
  useEffect(() => {
    setActionError(false);
  }, [connection]);

  useEffect(() => {
    setRevealed(false);
    setCopied(false);
    setCopyError(false);
    if (!challenge) return;
    const tick = () => {
      const current = Date.now();
      setNow(current);
      if (current >= challenge.expiresAt) {
        clearInterval(timer);
        onExpire.current?.();
      }
    };
    const timer = setInterval(tick, 1000);
    tick();
    return () => clearInterval(timer);
  }, [challenge]);

  const currentChallenge = challenge && challenge.expiresAt > now ? challenge : undefined;
  const blocked = Boolean(busy || uncertain || actionPending || actionError);
  const ready = mode === "ready" && connection;
  const seconds = currentChallenge
    ? Math.max(0, Math.ceil((currentChallenge.expiresAt - now) / 1000))
    : 0;

  async function copyCode() {
    if (!currentChallenge) return;
    try {
      await navigator.clipboard.writeText(currentChallenge.message);
      setCopied(true);
    } catch {
      setCopyError(true);
    }
  }

  async function performAction(kind: "link" | "unlink") {
    if (blocked || actionLock.current) return;
    actionLock.current = true;
    setActionPending(kind);
    try {
      if (kind === "link") await props.onLink?.();
      else if (await props.onDisconnect?.()) setConfirmDisconnect(false);
    } catch {
      setActionError(true);
    } finally {
      actionLock.current = false;
      setActionPending(null);
    }
  }

  return (
    <section className="whatsapp-panel" aria-labelledby="whatsapp-title">
      <header className="whatsapp-heading">
        <div>
          <WhatsappLogo size={28} aria-hidden />
          <h2 id="whatsapp-title">Wrytely on WhatsApp</h2>
        </div>
        {ready && (
          <span className="connection-status">
            {connection.linked ? "Connected" : "Not connected"}
          </span>
        )}
      </header>
      <p className="connection-lead">
        Send your agent a message. Keep your results and next steps close.
      </p>
      {mode === "signed-out" ? (
        <p>
          Sign in to connect your own WhatsApp.{" "}
          <a href="/sign-in" className="text-button">
            Sign in <ArrowUpRight size={16} aria-hidden />
          </a>
        </p>
      ) : mode === "unconfigured" || mode === "unavailable" ? (
        <p className="connection-notice">
          WhatsApp setup is not available yet. You can keep using your workspace while we finish
          connecting it.
        </p>
      ) : mode === "loading" ? (
        <p className="connection-notice" role="status">
          <CircleNotch size={18} className="spinner" aria-hidden /> Checking your WhatsApp
          connection…
        </p>
      ) : mode === "expired" ? (
        <p className="connection-notice" role="alert">
          Your session expired. <a href="/sign-in">Sign in again</a> to manage your connection.
        </p>
      ) : mode === "error" ? (
        <div className="connection-notice" role="alert">
          <p>We couldn’t check your connection. Your saved work is still there.</p>
          {props.onRefresh && (
            <button className="text-button" onClick={props.onRefresh}>
              Check connection
            </button>
          )}
        </div>
      ) : (
        ready && (
          <>
            {props.error && (
              <p className="connection-error" role="alert">
                {props.error}
              </p>
            )}
            {actionError && (
              <div className="connection-notice" role="alert">
                <p>We couldn’t confirm that change. Check your connection before trying again.</p>
                <button className="text-button" onClick={props.onRefresh}>
                  Check connection
                </button>
              </div>
            )}
            {uncertain && (
              <div className="connection-notice" role="status">
                <p>
                  We couldn’t confirm the last change. Check your connection before trying again.
                </p>
                <button className="text-button" disabled={Boolean(busy)} onClick={props.onRefresh}>
                  Check connection
                </button>
              </div>
            )}
            {connection.linked ? (
              <div className="connection-summary">
                <p>
                  <Check size={18} aria-hidden /> Verified number ending in{" "}
                  <strong>{connection.phoneLast4}</strong>
                </p>
                <p>Your number belongs to this workspace. Your message preferences are below.</p>
                {!confirmDisconnect ? (
                  <button
                    ref={disconnectButton}
                    className="text-button disconnect-button"
                    disabled={blocked}
                    onClick={() => setConfirmDisconnect(true)}
                  >
                    Disconnect WhatsApp
                  </button>
                ) : (
                  <div
                    className="disconnect-confirm"
                    role="group"
                    aria-label="Disconnect WhatsApp?"
                  >
                    <h3>Disconnect WhatsApp?</h3>
                    <p>
                      Queued replies will be cancelled. A message already being sent cannot be
                      recalled.
                    </p>
                    <div className="connection-actions">
                      <button
                        ref={keepConnectionButton}
                        className="quiet-button"
                        disabled={Boolean(busy || actionPending)}
                        onClick={() => {
                          setConfirmDisconnect(false);
                        }}
                      >
                        Keep connection
                      </button>
                      <button
                        className="quiet-button disconnect-button"
                        disabled={blocked || !props.onDisconnect}
                        onClick={() => void performAction("unlink")}
                      >
                        Confirm disconnect
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : !connection.configured || !connection.destination ? (
              <p className="connection-notice">
                The WhatsApp destination is not configured yet. Your workspace is still available.
              </p>
            ) : (
              <div className="verification-flow">
                <ol>
                  <li>
                    <strong>Create a verification message</strong>
                    <p>It expires in ten minutes and works once. Keep it private.</p>
                  </li>
                  <li>
                    <strong>Send it from your WhatsApp</strong>
                    <p>
                      Send the exact message to{" "}
                      <span className="destination-number">+{connection.destination}</span>.
                    </p>
                  </li>
                  <li>
                    <strong>Check your connection</strong>
                    <p>We’ll confirm the number after your message arrives.</p>
                  </li>
                </ol>
                {currentChallenge ? (
                  <div className="verification-message">
                    <label htmlFor="whatsapp-code">Verification message</label>
                    <input
                      id="whatsapp-code"
                      type={revealed ? "text" : "password"}
                      readOnly
                      value={currentChallenge.message}
                      autoComplete="off"
                      spellCheck={false}
                    />
                    <div className="connection-actions">
                      <button
                        className="quiet-button"
                        aria-pressed={revealed}
                        onClick={() => setRevealed(!revealed)}
                      >
                        {revealed ? "Hide verification message" : "Show verification message"}
                      </button>
                      <button className="quiet-button" onClick={() => void copyCode()}>
                        {copied ? "Copied" : "Copy message"}
                      </button>
                    </div>
                    {copyError && (
                      <p role="status">
                        Copy isn’t available here. Show the message and copy it manually.
                      </p>
                    )}
                    <p className="code-expiry">
                      Expires in {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}
                    </p>
                    <div className="connection-actions">
                      <a
                        className="quiet-button"
                        href={`https://wa.me/${connection.destination}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open WhatsApp <ArrowUpRight size={16} aria-hidden />
                      </a>
                      <button
                        className="primary-button"
                        disabled={blocked}
                        onClick={props.onRefresh}
                      >
                        Check connection
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    className="primary-button"
                    disabled={blocked || !props.onLink}
                    onClick={() => void performAction("link")}
                  >
                    {busy === "link" || actionPending === "link"
                      ? "Creating message…"
                      : "Create verification message"}
                  </button>
                )}
              </div>
            )}
            <PreferencesForm
              preferences={connection.preferences}
              disabled={blocked || !props.onSave}
              onSave={props.onSave}
            />
          </>
        )
      )}
    </section>
  );
}

function PreferencesForm({
  preferences,
  disabled,
  onSave,
}: {
  preferences: CommunicationPreferences | null;
  disabled: boolean;
  onSave?: Props["onSave"];
}) {
  const [draft, setDraft] = useState<CommunicationPreferences>(
    () =>
      preferences ?? {
        consent: false,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        quiet_start: 22,
        quiet_end: 7,
      },
  );
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [remoteChanged, setRemoteChanged] = useState(false);
  const preferencesKey = JSON.stringify(preferences);
  const lastPreferences = useRef(preferencesKey);
  const lock = useRef(false);
  const timezoneField = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (lastPreferences.current === preferencesKey) return;
    lastPreferences.current = preferencesKey;
    if (dirty) {
      setRemoteChanged(true);
      return;
    }
    setDraft(
      preferences ?? {
        consent: false,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        quiet_start: 22,
        quiet_end: 7,
      },
    );
    setSaved(false);
  }, [preferencesKey, preferences, dirty]);
  function edit(patch: Partial<CommunicationPreferences>) {
    setDraft({ ...draft, ...patch });
    setSaved(false);
    setError(null);
    setDirty(true);
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (disabled || lock.current || !onSave) return;
    try {
      new Intl.DateTimeFormat("en-US", { timeZone: draft.timezone }).format();
    } catch {
      setError("Choose a valid timezone, such as America/Denver.");
      timezoneField.current?.focus();
      return;
    }
    lock.current = true;
    setSubmitting(true);
    try {
      if (await onSave(draft)) {
        setSaved(true);
        setDirty(false);
        setRemoteChanged(false);
      }
    } finally {
      lock.current = false;
      setSubmitting(false);
    }
  }
  return (
    <form className="communication-preferences" noValidate onSubmit={save}>
      <h3>Messages on your terms</h3>
      <p>
        Choose when Wrytely may contact you. These settings won’t connect a number by themselves.
      </p>
      {!preferences && !saved && (
        <p className="preferences-unsaved">Preferences have not been saved yet.</p>
      )}
      {remoteChanged && (
        <div className="connection-notice" role="status">
          <p>Saved preferences changed. Your unsaved edits are kept; review them before saving.</p>
          <button
            className="text-button"
            type="button"
            onClick={() => {
              if (preferences) setDraft(preferences);
              setDirty(false);
              setRemoteChanged(false);
              setError(null);
            }}
          >
            Use saved preferences
          </button>
        </div>
      )}
      <label className="consent-field">
        <input
          type="checkbox"
          checked={draft.consent}
          disabled={disabled || submitting}
          onChange={(e) => edit({ consent: e.target.checked })}
        />{" "}
        Allow Wrytely to send me WhatsApp replies
      </label>
      <div className="preference-fields">
        <div>
          <label htmlFor="student-timezone">Your timezone</label>
          <input
            id="student-timezone"
            ref={timezoneField}
            value={draft.timezone}
            disabled={disabled || submitting}
            onChange={(e) => edit({ timezone: e.target.value })}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "timezone-error" : "timezone-help"}
          />
          <p id="timezone-help">For example, America/Denver. Check the suggestion before saving.</p>
          {error && (
            <p id="timezone-error" className="connection-error" role="alert">
              {error}
            </p>
          )}
        </div>
        <fieldset disabled={disabled || submitting}>
          <legend>Quiet hours</legend>
          <div className="quiet-hour-fields">
            <label>
              From
              <select
                value={draft.quiet_start}
                onChange={(e) => edit({ quiet_start: Number(e.target.value) })}
              >
                {Array.from({ length: 24 }, (_, hour) => (
                  <option key={hour} value={hour}>
                    {String(hour).padStart(2, "0")}:00
                  </option>
                ))}
              </select>
            </label>
            <label>
              Until
              <select
                value={draft.quiet_end}
                onChange={(e) => edit({ quiet_end: Number(e.target.value) })}
              >
                {Array.from({ length: 24 }, (_, hour) => (
                  <option key={hour} value={hour}>
                    {String(hour).padStart(2, "0")}:00
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p>Use the same hour to turn quiet hours off.</p>
        </fieldset>
      </div>
      <div className="connection-actions">
        <button className="primary-button" type="submit" disabled={disabled || submitting}>
          {submitting ? "Saving…" : "Save preferences"}
        </button>
        {saved && <span role="status">Preferences saved.</span>}
      </div>
    </form>
  );
}
