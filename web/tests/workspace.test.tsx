import { afterEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import { Workspace } from "../components/workspace";
import { readDraft, useWorkspace } from "../lib/use-workspace";

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
const taskId = "00000000-0000-0000-0000-000000000001";
function backend(loseFirst = false) {
  let submissions = 0;
  return vi.fn<typeof fetch>(async (input, options) => {
    const path = String(input);
    if (path.endsWith("bootstrap"))
      return Response.json({ id: "agent_alice", user_id: "user_alice", paused: false });
    if (path.endsWith("messages") && options?.method === "POST") {
      submissions++;
      if (loseFirst && submissions === 1)
        throw new TypeError("Network lost after accepting message");
      return Response.json({ task_id: taskId, status: "ready" }, { status: 202 });
    }
    if (path.endsWith("tasks")) return Response.json({ tasks: [] });
    if (path.includes("tasks/")) return Response.json({ id: taskId, status: "done" });
    return Response.json({ messages: [] });
  });
}
describe("student workspace", () => {
  it("clears hidden context and the whole workspace on a result-status session expiry", async () => {
    const base = backend();
    const source = {
      source_id: taskId,
      version_id: taskId,
      title: "Fictional policy",
      reference: "demo",
      coverage: "snapshot",
      retrieved_at: "2026-10-29T00:00:00Z",
      external_revision: "1",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (url, options) => {
        const path = String(url);
        if (path.endsWith("/sources")) return Response.json({ sources: [source], limit: 50 });
        if (path.endsWith("/responsibilities"))
          return Response.json({
            responsibilities: [
              {
                id: taskId,
                objective: "Private comparison",
                status: "active",
                steps_created: 1,
                max_steps: 6,
                created_at: source.retrieved_at,
              },
            ],
            limit: 50,
          });
        if (path.endsWith("/status")) return Response.json({ detail: "Expired" }, { status: 401 });
        if (path.endsWith("/artifacts")) return Response.json({ artifacts: [], limit: 50 });
        return base(url, options);
      }),
    );
    render(<Workspace mode="signed-in" userId="user_alice" />);
    await screen.findByRole("button", { name: "Pause agent" });
    fireEvent.click(screen.getByRole("button", { name: "Academic context" }));
    fireEvent.change(screen.getByLabelText("Pasted text"), {
      target: { value: "Unsaved private text" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Private results" }));
    fireEvent.click(await screen.findByRole("button", { name: "Open work: Private comparison" }));
    await screen.findByRole("heading", { name: "Your session expired" });
    expect(screen.queryByRole("button", { name: "Academic context" })).toBeNull();
    expect(screen.queryByLabelText("Pasted text")).toBeNull();
    expect(screen.queryByText("Private comparison")).toBeNull();
  });
  it("keeps the snapshot draft when navigating away and back without submitting it", async () => {
    const base = backend();
    const fetcher = vi.fn<typeof fetch>(async (url, options) =>
      String(url).endsWith("/sources")
        ? Response.json({ sources: [], limit: 50 })
        : base(url, options),
    );
    vi.stubGlobal("fetch", fetcher);
    render(<Workspace mode="signed-in" userId="user_alice" name="Alice" />);
    await screen.findByRole("button", { name: "Pause agent" });
    fireEvent.click(screen.getByRole("button", { name: "Academic context" }));
    fireEvent.change(screen.getByLabelText("Pasted text"), {
      target: { value: "Unsaved synthetic source" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Overview" }));
    expect(screen.queryByRole("textbox", { name: "Pasted text" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Academic context" }));
    expect((screen.getByLabelText("Pasted text") as HTMLTextAreaElement).value).toBe(
      "Unsaved synthetic source",
    );
    expect(
      fetcher.mock.calls.filter(
        ([, opts]) =>
          opts?.method === "POST" && String(opts.body).includes("Unsaved synthetic source"),
      ),
    ).toHaveLength(0);
  });
  it("refreshes saved work without opening conversation and stops while paused", async () => {
    vi.useFakeTimers();
    const fetch = backend();
    vi.stubGlobal("fetch", fetch);
    const { result } = renderHook(() => useWorkspace("user_alice"));
    await act(async () => {});
    expect(result.current.loading).toBe(false);
    const taskReads = () =>
      fetch.mock.calls.filter(([url]) => String(url).endsWith("/tasks")).length;
    expect(taskReads()).toBe(1);
    await act(() => vi.advanceTimersByTimeAsync(10000));
    expect(taskReads()).toBe(2);
    fetch.mockResolvedValue(
      Response.json({ id: "agent_alice", user_id: "user_alice", paused: true }),
    );
    await act(() => result.current.togglePause());
    await act(() => vi.advanceTimersByTimeAsync(30000));
    expect(taskReads()).toBe(2);
  });
  it("shows an honest public shell and makes no private requests", () => {
    const fetch = backend();
    vi.stubGlobal("fetch", fetch);
    render(<Workspace mode="unconfigured" />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
      "Your semester, moving forward",
    );
    expect(screen.queryByRole("textbox", { name: "Message Wrytely" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /See connections/ }));
    expect(screen.getByText("No courses or chats are connected yet.")).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
  });
  it("offers real auth routes when configured but signed out", () => {
    render(<Workspace mode="signed-out" />);
    expect(screen.getByRole("link", { name: /Set up your agent/ }).getAttribute("href")).toBe(
      "/sign-up",
    );
    expect(screen.getByRole("link", { name: /Sign in/ }).getAttribute("href")).toBe("/sign-in");
  });
  it("keeps a draft when moving between the overview and conversation", async () => {
    vi.stubGlobal("fetch", backend());
    render(<Workspace mode="signed-in" userId="user_alice" name="Alice" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Pause agent" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Conversation" }));
    await waitFor(() =>
      expect(
        (screen.getByRole("textbox", { name: "Message Wrytely" }) as HTMLTextAreaElement).disabled,
      ).toBe(false),
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Message Wrytely" }), {
      target: { value: "My unsent thought" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Overview" }));
    expect(screen.queryByRole("textbox")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Conversation" }));
    expect(
      (screen.getByRole("textbox", { name: "Message Wrytely" }) as HTMLTextAreaElement).value,
    ).toBe("My unsent thought");
  });
  it("reuses a persisted key after an uncertain send and a remount", async () => {
    const fetch = backend(true);
    vi.stubGlobal("fetch", fetch);
    const first = renderHook(() => useWorkspace("user_alice"));
    await waitFor(() => expect(first.result.current.loading).toBe(false));
    act(() => first.result.current.edit("Help me start this assignment"));
    await act(() => first.result.current.send());
    expect(first.result.current.uncertain).toBe(true);
    const saved = readDraft("wrytely:draft:user_alice");
    expect(saved.pending?.content).toBe("Help me start this assignment");
    first.unmount();
    const second = renderHook(() => useWorkspace("user_alice"));
    await waitFor(() => expect(second.result.current.loading).toBe(false));
    expect(second.result.current.uncertain).toBe(true);
    await act(() => second.result.current.send());
    const posts = fetch.mock.calls.filter(
      ([, options]) => options?.method === "POST" && String(options?.body).includes("Help me"),
    );
    expect(posts).toHaveLength(2);
    expect(posts[0][1]?.headers).toEqual(posts[1][1]?.headers);
    expect(second.result.current.task?.id).toBe(taskId);
    expect(second.result.current.draft).toBe("");
    expect(readDraft("wrytely:draft:user_alice").pending).toBeUndefined();
  });
  it("does not load another account's draft or unresolved submission", async () => {
    sessionStorage.setItem(
      "wrytely:draft:user_alice",
      JSON.stringify({
        text: "Private draft",
        pending: { key: "private-key", content: "Private draft" },
      }),
    );
    vi.stubGlobal("fetch", backend());
    const { result } = renderHook(() => useWorkspace("user_bob"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.draft).toBe("");
    expect(result.current.uncertain).toBe(false);
  });
  it("retains the unsent draft when authentication expires", async () => {
    const fetch = backend();
    vi.stubGlobal("fetch", fetch);
    const { result } = renderHook(() => useWorkspace("user_alice"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.edit("Do not lose this"));
    fetch.mockResolvedValue(Response.json({ detail: "Sign in again" }, { status: 401 }));
    await act(() => result.current.send());
    expect(result.current.expired).toBe(true);
    expect(result.current.draft).toBe("Do not lose this");
    expect(readDraft("wrytely:draft:user_alice").pending).toBeTruthy();
  });
  it("confirms pause with the backend before showing the agent as paused", async () => {
    const fetch = backend();
    vi.stubGlobal("fetch", fetch);
    render(<Workspace mode="signed-in" userId="user_alice" name="Alice" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Pause agent" })).toBeTruthy());
    fetch.mockResolvedValue(
      Response.json({ id: "agent_alice", user_id: "user_alice", paused: true }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Pause agent" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Resume agent" }).getAttribute("aria-pressed"),
      ).toBe("true"),
    );
    const call = fetch.mock.calls.find(([url]) => String(url).endsWith("agent/control"));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ paused: true });
    expect(screen.getByText("Work stays saved while paused.")).toBeTruthy();
  });
});
