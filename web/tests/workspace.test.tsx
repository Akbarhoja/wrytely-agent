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
    if (path.includes("tasks/")) return Response.json({ id: taskId, status: "done" });
    return Response.json({ messages: [] });
  });
}
describe("student workspace", () => {
  it("shows an honest public shell and makes no private requests", () => {
    const fetch = backend();
    vi.stubGlobal("fetch", fetch);
    render(<Workspace mode="unconfigured" />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("A little less");
    expect(
      (screen.getByRole("button", { name: "Send message" }) as HTMLButtonElement).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: /See connections/ }));
    expect(screen.getByText("No courses or chats are connected yet.")).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
  });
  it("offers real auth routes when configured but signed out", () => {
    render(<Workspace mode="signed-out" />);
    expect(screen.getByRole("link", { name: /Create your workspace/ }).getAttribute("href")).toBe(
      "/sign-up",
    );
    expect(screen.getByRole("link", { name: /Sign in/ }).getAttribute("href")).toBe("/sign-in");
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
    expect(screen.getByText("Paused · messages will wait")).toBeTruthy();
  });
});
