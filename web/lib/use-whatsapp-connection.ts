"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./client";
import type {
  CommunicationPreferences,
  ConnectionView,
  LinkChallenge,
} from "../components/whatsapp-connection";

type Status = {
  linked: boolean;
  phone_last4: string | null;
  destination: string | null;
  configured: boolean;
  preferences: CommunicationPreferences | null;
  latest_delivery: { state: string; reason: string | null; retry_at: string | null } | null;
};
type State = {
  owner?: string;
  connection?: ConnectionView;
  challenge?: LinkChallenge;
  mode: "loading" | "ready" | "error" | "expired";
  busy: string | null;
  uncertain: boolean;
  error: string | null;
};
const initial: State = { mode: "loading", busy: null, uncertain: false, error: null };

export function useWhatsAppConnection(userId?: string) {
  const [state, setState] = useState<State>(initial);
  const session = useRef<{
    owner?: string;
    abort: AbortController;
    locked: boolean;
    uncertain: boolean;
  } | null>(null);

  const read = useCallback(async (scope: NonNullable<typeof session.current>) => {
    const result = await api<Status>("whatsapp", { signal: scope.abort.signal });
    if (scope.abort.signal.aborted || session.current !== scope) return undefined;
    const connection: ConnectionView = {
      linked: result.linked,
      phoneLast4: result.phone_last4,
      destination: result.destination,
      configured: result.configured,
      preferences: result.preferences,
      delivery: result.latest_delivery
        ? {
            state: result.latest_delivery.state,
            reason: result.latest_delivery.reason,
            retryAt: result.latest_delivery.retry_at,
          }
        : null,
    };
    scope.uncertain = false;
    setState((previous) => ({
      ...previous,
      owner: scope.owner,
      connection,
      mode: "ready",
      uncertain: false,
      error: null,
      challenge: connection.linked ? undefined : previous.challenge,
    }));
    return connection;
  }, []);

  const report = useCallback(
    (scope: NonNullable<typeof session.current>, failure: unknown, mutation: boolean) => {
      if (scope.abort.signal.aborted || session.current !== scope) return;
      const expired = failure instanceof ApiError && failure.status === 401;
      const inaccessible = failure instanceof ApiError && [403, 404].includes(failure.status);
      const rejected =
        failure instanceof ApiError && [401, 403, 409, 413, 415, 422, 429].includes(failure.status);
      if (mutation && !rejected) scope.uncertain = true;
      setState((previous) => ({
        ...previous,
        owner: scope.owner,
        connection: expired || inaccessible ? undefined : previous.connection,
        challenge: undefined,
        mode: expired ? "expired" : inaccessible || !mutation ? "error" : previous.mode,
        uncertain: scope.uncertain,
        error:
          failure instanceof ApiError
            ? failure.message
            : "The connection was interrupted. Check your connection before trying again.",
      }));
    },
    [],
  );

  useEffect(() => {
    const scope = { owner: userId, abort: new AbortController(), locked: false, uncertain: false };
    session.current = scope;
    setState({ ...initial, owner: userId });
    if (userId) void read(scope).catch((failure) => report(scope, failure, false));
    return () => {
      scope.abort.abort();
    };
  }, [userId, read, report]);

  async function refresh() {
    const scope = session.current;
    if (!userId || scope?.owner !== userId || scope.abort.signal.aborted || scope.locked) return;
    scope.locked = true;
    setState((previous) => ({ ...previous, busy: "refresh" }));
    try {
      await read(scope);
    } catch (failure) {
      report(scope, failure, false);
    } finally {
      scope.locked = false;
      if (!scope.abort.signal.aborted) setState((previous) => ({ ...previous, busy: null }));
    }
  }

  async function mutate(
    kind: "link" | "unlink" | "preferences",
    preferences?: CommunicationPreferences,
  ) {
    const scope = session.current;
    if (
      !userId ||
      scope?.owner !== userId ||
      scope.abort.signal.aborted ||
      scope.locked ||
      scope.uncertain ||
      state.mode !== "ready"
    )
      return false;
    scope.locked = true;
    setState((previous) => ({ ...previous, busy: kind, error: null }));
    try {
      const requestStartedAt = Date.now();
      const result = await api<{ message?: string; expires_in_seconds?: number }>(
        `whatsapp/${kind}`,
        {
          method: "POST",
          body: JSON.stringify(preferences ?? {}),
          signal: scope.abort.signal,
        },
      );
      if (scope.abort.signal.aborted || session.current !== scope) return false;
      if (kind === "link") {
        const lifetime = result.expires_in_seconds;
        const expiresAt = requestStartedAt + (typeof lifetime === "number" ? lifetime * 1000 : NaN);
        if (
          !result.message ||
          typeof lifetime !== "number" ||
          !Number.isInteger(lifetime) ||
          lifetime <= 0 ||
          lifetime > 600 ||
          expiresAt <= Date.now()
        )
          throw new Error("Invalid challenge response");
        setState((previous) => ({
          ...previous,
          challenge: { message: result.message!, expiresAt },
        }));
        return true;
      }
      // A successful POST is followed by an authoritative read; never invent saved state.
      const connection = await read(scope);
      if (kind === "unlink") return Boolean(connection && !connection.linked);
      const saved = connection?.preferences;
      return Boolean(
        saved &&
        preferences &&
        Object.keys(preferences).every(
          (key) =>
            saved[key as keyof CommunicationPreferences] ===
            preferences[key as keyof CommunicationPreferences],
        ),
      );
    } catch (failure) {
      report(scope, failure, true);
      return false;
    } finally {
      scope.locked = false;
      if (!scope.abort.signal.aborted) setState((previous) => ({ ...previous, busy: null }));
    }
  }

  // Guard the render before effects run, and ignore responses from aborted accounts.
  const visible = state.owner === userId && userId ? state : initial;
  return {
    ...visible,
    onRefresh: refresh,
    onLink: async () => {
      await mutate("link");
    },
    onDisconnect: () => mutate("unlink"),
    onSave: (preferences: CommunicationPreferences) => mutate("preferences", preferences),
    onExpire: () => setState((previous) => ({ ...previous, challenge: undefined })),
  };
}
