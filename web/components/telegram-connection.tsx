"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../lib/client";

type Preferences = {
  consent: boolean;
  notification_consent: boolean;
  timezone: string;
  quiet_start: number;
  quiet_end: number;
};
type Status = {
  linked: boolean;
  preferences: Preferences | null;
  bot_username: string | null;
  latest_delivery: { state: string; reason: string | null } | null;
};
const defaults: Preferences = {
  consent: false,
  notification_consent: false,
  timezone: "UTC",
  quiet_start: 22,
  quiet_end: 8,
};

export function TelegramConnection(props: {
  userId: string;
  enabled: boolean;
  onSessionExpired?: () => void;
}) {
  return <Session key={`${props.userId}:${props.enabled}`} {...props} />;
}
function Session({
  enabled,
  onSessionExpired,
}: {
  userId: string;
  enabled: boolean;
  onSessionExpired?: () => void;
}) {
  const [status, setStatus] = useState<Status | null>(null),
    [prefs, setPrefs] = useState<Preferences>(defaults),
    [challenge, setChallenge] = useState<{
      message: string;
      expires_at: string;
      bot_username: string | null;
    } | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const request = useRef<AbortController | null>(null);
  const [expired, setExpired] = useState(false);
  async function read(signal: AbortSignal) {
    const value = await api<Status>("telegram", { signal });
    if (
      typeof value?.linked !== "boolean" ||
      (value.preferences !== null &&
        (typeof value.preferences?.consent !== "boolean" ||
          typeof value.preferences.notification_consent !== "boolean" ||
          typeof value.preferences.timezone !== "string" ||
          !Number.isInteger(value.preferences.quiet_start) ||
          !Number.isInteger(value.preferences.quiet_end)))
    )
      throw Error();
    if (!signal.aborted) {
      setStatus(value);
      setPrefs(value.preferences ?? defaults);
      if (value.linked) setChallenge(null);
    }
  }
  async function run(work: (signal: AbortSignal) => Promise<void>) {
    if (!enabled || expired || request.current) return;
    const control = new AbortController();
    request.current = control;
    setBusy(true);
    setError("");
    try {
      await work(control.signal);
    } catch (e) {
      if (!control.signal.aborted) {
        setChallenge(null);
        setStatus(null);
        setError("Could not update Telegram. Refresh to check saved state.");
        if (e instanceof ApiError && e.status === 401) {
          setExpired(true);
          onSessionExpired?.();
        }
      }
    } finally {
      if (!control.signal.aborted) {
        setBusy(false);
        request.current = null;
      }
    }
  }
  useEffect(() => {
    if (enabled) void run(read);
    return () => {
      request.current?.abort();
      request.current = null;
    };
  }, [enabled]);
  useEffect(() => {
    if (!challenge) return;
    const delay = Date.parse(challenge.expires_at) - Date.now();
    if (!Number.isFinite(delay) || delay <= 0) {
      setChallenge(null);
      return;
    }
    const timer = setTimeout(() => setChallenge(null), Math.min(delay, 600000));
    return () => clearTimeout(timer);
  }, [challenge]);
  async function link(signal: AbortSignal) {
    const value = await api<{ message: string; expires_at: string; bot_username: string | null }>(
      "telegram/link",
      { method: "POST", signal },
    );
    if (
      !/^\/start [A-Za-z0-9_-]{43}$/.test(value.message) ||
      !Number.isFinite(Date.parse(value.expires_at))
    )
      throw Error();
    if (!signal.aborted) setChallenge(value);
  }
  const username = challenge?.bot_username ?? status?.bot_username;
  const trustedUsername =
    typeof username === "string" && /^[A-Za-z0-9_]{5,32}$/.test(username) ? username : null;
  return (
    <section className="whatsapp-panel" aria-label="Telegram fallback connection" aria-busy={busy}>
      <header className="whatsapp-heading">
        <h2>Telegram fallback</h2>
        <span>{status?.linked ? "Linked" : "Not linked"}</span>
      </header>
      <p className="connection-lead">
        Private preparation checklists and replies. WhatsApp remains separate and inactive while
        verification is pending. Telegram does not support /accept, /file or /revise yet.
      </p>
      {!enabled ? (
        <p>Sign in to manage Telegram.</p>
      ) : (
        <>
          {error && <p role="alert">{error}</p>}
          <button className="text-button" disabled={busy || expired} onClick={() => void run(read)}>
            Refresh Telegram
          </button>
          {!status?.linked && !challenge && (
            <button
              className="text-button"
              disabled={busy || expired}
              onClick={() => void run(link)}
            >
              Create private link message
            </button>
          )}
          {challenge && (
            <div className="connection-notice">
              <p>
                Send this one-use message only to{" "}
                {trustedUsername ? `@${trustedUsername}` : "the configured Wrytely bot"}. It expires
                in 10 minutes. Keep it private.
              </p>
              <label>
                Private link message
                <input readOnly value={challenge.message} />
              </label>
              {trustedUsername && (
                <a
                  className="text-button"
                  href={`https://t.me/${trustedUsername}?start=${challenge.message.slice(7)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open configured Telegram bot
                </a>
              )}
            </div>
          )}
          {status?.linked && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void run(async (signal) => {
                  await api("telegram/preferences", {
                    method: "POST",
                    signal,
                    body: JSON.stringify(prefs),
                  });
                  await read(signal);
                });
              }}
            >
              <fieldset disabled={busy || expired}>
                <legend>Separate Telegram permissions</legend>
                <label>
                  <input
                    type="checkbox"
                    checked={prefs.consent}
                    onChange={(e) => setPrefs({ ...prefs, consent: e.target.checked })}
                  />
                  Allow Telegram replies
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={prefs.notification_consent}
                    onChange={(e) => setPrefs({ ...prefs, notification_consent: e.target.checked })}
                  />
                  Allow preparation notifications
                </label>
                <label>
                  Timezone
                  <input
                    value={prefs.timezone}
                    onChange={(e) => setPrefs({ ...prefs, timezone: e.target.value })}
                    required
                    maxLength={100}
                  />
                </label>
                <label>
                  Quiet hours start
                  <input
                    type="number"
                    min={0}
                    max={23}
                    value={prefs.quiet_start}
                    onChange={(e) => setPrefs({ ...prefs, quiet_start: Number(e.target.value) })}
                  />
                </label>
                <label>
                  Quiet hours end
                  <input
                    type="number"
                    min={0}
                    max={23}
                    value={prefs.quiet_end}
                    onChange={(e) => setPrefs({ ...prefs, quiet_end: Number(e.target.value) })}
                  />
                </label>
                <p>
                  Equal hours disable quiet hours when you save. /stop pauses your agent and
                  disables Telegram permissions. Linking alone does not grant permission.
                </p>
                <button className="text-button" type="submit">
                  Save Telegram permissions
                </button>
              </fieldset>
            </form>
          )}
          {status?.linked && (
            <button
              className="text-button"
              disabled={busy || expired}
              onClick={() =>
                void run(async (signal) => {
                  await api("telegram/unlink", { method: "POST", signal });
                  setChallenge(null);
                  await read(signal);
                })
              }
            >
              Unlink Telegram
            </button>
          )}
          {status?.latest_delivery && (
            <p>
              Last provider outcome: {status.latest_delivery.state}. Accepted does not mean received
              or read.
            </p>
          )}
          {busy && <p role="status">Updating Telegram…</p>}
        </>
      )}
    </section>
  );
}
