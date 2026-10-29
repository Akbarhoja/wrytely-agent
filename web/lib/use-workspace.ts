"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  ApiError,
  submitMessage,
  type Agent,
  type Message,
  type Submission,
  type Task,
  type WorkItem,
} from "./client";

type Draft = { text: string; pending?: Submission; task?: string };
export function readDraft(key: string): Draft {
  try {
    const value = JSON.parse(sessionStorage.getItem(key) || "{}");
    const text = typeof value.text === "string" ? value.text.slice(0, 12000) : "";
    const pending =
      value.pending &&
      typeof value.pending.content === "string" &&
      value.pending.content.length <= 12000 &&
      typeof value.pending.key === "string" &&
      value.pending.key.length <= 128
        ? (value.pending as Submission)
        : undefined;
    const task =
      typeof value.task === "string" && /^[0-9a-f-]{36}$/i.test(value.task)
        ? value.task
        : undefined;
    return { text, pending, task };
  } catch {
    return { text: "" };
  }
}

export function useWorkspace(userId?: string) {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [task, setTask] = useState<Task | null>(null);
  const [work, setWork] = useState<WorkItem[]>([]);
  const [workLoaded, setWorkLoaded] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [loading, setLoading] = useState(Boolean(userId));
  const [sending, setSending] = useState(false);
  const [changing, setChanging] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [revision, setRevision] = useState(0);
  const pending = useRef<Submission | undefined>(undefined);
  const storedTask = useRef<string | undefined>(undefined);
  const controller = useRef<AbortController | null>(null);
  const sendingLock = useRef(false);
  const storageKey = `wrytely:draft:${userId}`;

  const persist = useCallback(
    (text: string) => {
      try {
        sessionStorage.setItem(
          storageKey,
          JSON.stringify({ text, pending: pending.current, task: storedTask.current }),
        );
      } catch {
        /* Storage may be unavailable; keep the current tab's in-memory draft. */
      }
    },
    [storageKey],
  );
  const report = useCallback((failure: unknown) => {
    if (failure instanceof DOMException && failure.name === "AbortError") return;
    setExpired(failure instanceof ApiError && failure.status === 401);
    setError(
      failure instanceof ApiError ? failure.message : "Connection interrupted. Please try again.",
    );
  }, []);
  const refreshMessages = useCallback(async (signal?: AbortSignal) => {
    const [result, activity] = await Promise.all([
      api<{ messages: Message[] }>("messages", { signal }),
      api<{ tasks: WorkItem[] }>("tasks", { signal }),
    ]);
    if (signal?.aborted) return;
    setMessages(result.messages);
    setWork(activity.tasks);
    setWorkLoaded(true);
  }, []);
  const refreshWork = useCallback(async (signal?: AbortSignal) => {
    const result = await api<{ tasks: WorkItem[] }>("tasks", { signal });
    if (signal?.aborted) return;
    setWork(result.tasks);
    setWorkLoaded(true);
  }, []);

  useEffect(() => {
    if (!userId) return;
    const abort = new AbortController();
    controller.current = abort;
    const saved = readDraft(storageKey);
    setDraft(saved.text);
    pending.current = saved.pending;
    storedTask.current = saved.task;
    setUncertain(Boolean(saved.pending));
    setLoading(true);
    setError(null);
    setExpired(false);
    async function load() {
      try {
        const profile = await api<Agent>("bootstrap", {
          method: "POST",
          body: "{}",
          signal: abort.signal,
        });
        if (abort.signal.aborted) return;
        setAgent(profile);
        await refreshMessages(abort.signal);
        if (saved.task) setTask(await api<Task>(`tasks/${saved.task}`, { signal: abort.signal }));
      } catch (failure) {
        if (!abort.signal.aborted) report(failure);
      } finally {
        if (!abort.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => abort.abort();
  }, [userId, storageKey, revision, report, refreshMessages]);

  // Watch saved work from other tabs and later background sources, even with chat closed.
  useEffect(() => {
    if (!userId || !agent || agent.paused || loading || expired) return;
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        await refreshWork(abort.signal);
        if (!abort.signal.aborted) timer = setTimeout(refresh, document.hidden ? 30000 : 10000);
      } catch (failure) {
        if (!abort.signal.aborted) report(failure);
      }
    }
    timer = setTimeout(refresh, 10000);
    return () => {
      clearTimeout(timer);
      abort.abort();
    };
  }, [userId, agent?.id, agent?.paused, loading, expired, revision, refreshWork, report]);

  useEffect(() => {
    if (!task || !["ready", "running"].includes(task.status) || agent?.paused) return;
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await api<Task>(`tasks/${task!.id}`, { signal: abort.signal });
        if (abort.signal.aborted) return;
        setTask(next);
        if (["done", "blocked"].includes(next.status)) {
          storedTask.current = undefined;
          persist(draft);
          await refreshMessages(abort.signal);
        } else {
          timer = setTimeout(poll, document.hidden ? 10000 : 2000);
        }
      } catch (failure) {
        if (!abort.signal.aborted) report(failure);
      }
    }
    timer = setTimeout(poll, 1000);
    return () => {
      clearTimeout(timer);
      abort.abort();
    };
  }, [task?.id, task?.status, agent?.paused, revision, draft, persist, refreshMessages, report]);

  function edit(value: string) {
    setDraft(value);
    persist(value);
  }
  async function send() {
    if (!agent || !userId || sendingLock.current || loading || expired) return;
    const submission = pending.current || { key: crypto.randomUUID(), content: draft.trim() };
    if (!submission.content) return;
    pending.current = submission;
    persist(draft);
    sendingLock.current = true;
    setSending(true);
    setError(null);
    try {
      const accepted = await submitMessage(submission, controller.current?.signal);
      if (controller.current?.signal.aborted) return;
      storedTask.current = accepted.task_id;
      pending.current = undefined;
      setUncertain(false);
      setDraft("");
      persist("");
      setTask({ id: accepted.task_id, status: accepted.status });
      try {
        await refreshMessages(controller.current?.signal);
      } catch (failure) {
        report(failure);
      }
    } catch (failure) {
      if (controller.current?.signal.aborted) return;
      // Uncertain network outcomes MUST retain the key and original content for retry.
      const rejected =
        failure instanceof ApiError && [409, 413, 415, 422, 429].includes(failure.status);
      if (rejected) {
        pending.current = undefined;
        persist(draft);
      }
      setUncertain(!rejected);
      report(failure);
    } finally {
      sendingLock.current = false;
      setSending(false);
    }
  }
  async function togglePause() {
    if (!agent || changing) return;
    setChanging(true);
    setError(null);
    try {
      setAgent(
        await api<Agent>("agent/control", {
          method: "POST",
          body: JSON.stringify({ paused: !agent.paused }),
          signal: controller.current?.signal,
        }),
      );
    } catch (failure) {
      report(failure);
    } finally {
      setChanging(false);
    }
  }
  return {
    agent,
    messages,
    task,
    work,
    workLoaded,
    draft,
    edit,
    send,
    togglePause,
    error,
    expired,
    loading,
    sending,
    changing,
    uncertain,
    retry: () => setRevision((value) => value + 1),
  };
}
