import { afterEach, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { StrictMode } from "react";
import { CanvasConnection } from "../components/canvas-connection";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const id = "00000000-0000-4000-8000-000000000001";
const connection = {
  connection_id: id,
  origin: "https://canvas.example.edu",
  state: "connected",
  generation: 2,
};
function mock(emptyScope = false) {
  const fetch = vi.fn(async (url: unknown, init?: RequestInit) => {
    const path = String(url);
    if (path.endsWith("/canvas/setup")) return Response.json({ origins: [connection.origin] });
    if (path.endsWith("/canvas/coverage"))
      return Response.json({
        connection,
        scope: {
          mode: emptyScope ? "explicit_set" : "all_active",
          resource_kinds: emptyScope ? [] : ["files"],
          ...(emptyScope ? { course_ids: [] } : {}),
        },
        discovery: { coverage: "complete", last_attempt_at: null, last_complete_at: null },
        scan: { state: "finished", started_at: null },
        evaluated_at: "2026-11-02T01:00:00Z",
        next: null,
        courses: [
          {
            course_id: "101",
            title: "Synthetic course",
            selected: !emptyScope,
            missing_pending_confirmation: false,
            resources: [
              {
                kind: "files",
                coverage: "complete",
                reason: null,
                items_seen: 3,
                retained_items: 3,
                incomplete_items: 2,
              },
            ],
          },
        ],
      });
    if (path.endsWith("/canvas/pairing"))
      return Response.json({
        code: "private-code",
        expires_at: new Date(Date.now() + 600000).toISOString(),
      });
    if (init?.method === "POST") return Response.json({});
    return Response.json({ connections: [connection], next_cursor: null });
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}
it("shows incomplete content even for a finished complete resource scan", async () => {
  mock();
  render(<CanvasConnection userId="alice" />);
  fireEvent.click(await screen.findByText("View courses and coverage"));
  await screen.findByText(/Latest scan: finished/);
  expect(screen.getByText(/2 with content gaps/)).toBeTruthy();
  expect(screen.getByText(/cannot see changes until the next sync/)).toBeTruthy();
  expect(screen.queryByText("Up to date")).toBeNull();
});
it("labels a finished empty-scope scan as discovery only and explains how to collect content", async () => {
  mock(true);
  render(<CanvasConnection userId="alice" />);
  fireEvent.click(await screen.findByText("View courses and coverage"));
  await screen.findByText(/Latest scan: course discovery finished/);
  expect(screen.getByText(/No course content is selected/)).toBeTruthy();
  expect(screen.getByText(/Pairing again clears your course selection/)).toBeTruthy();
  expect(screen.queryByText(/Latest scan: finished/)).toBeNull();
});
it("scope choice sends only verified connection controls, never a posted account id", async () => {
  const fetch = mock();
  render(<CanvasConnection userId="alice" />);
  fireEvent.click(await screen.findByText("Read all active courses"));
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([url, init]) => String(url).endsWith("/canvas/scope") && init?.method === "POST",
      ),
    ).toBe(true),
  );
  const payload = JSON.parse(
    fetch.mock.calls.find(([url]) => String(url).endsWith("/canvas/scope"))![1]!.body as string,
  );
  expect(payload.connection_id).toBe(id);
  expect(payload.generation).toBe(2);
  expect(payload.mode).toBe("all_active");
  expect(payload.course_ids).toEqual([]);
  expect(payload).not.toHaveProperty("user_id");
});
it("changing account clears private pairing code immediately", async () => {
  mock();
  const view = render(<CanvasConnection userId="alice" />);
  fireEvent.click(await screen.findByText("Create linking code"));
  await screen.findByText("private-code");
  view.rerender(<CanvasConnection userId="bob" />);
  expect(screen.queryByText("private-code")).toBeNull();
});

it("loads under React Strict Mode effect cleanup and replay", async () => {
  mock();
  render(
    <StrictMode>
      <CanvasConnection userId="alice" />
    </StrictMode>,
  );
  await screen.findByText("View courses and coverage");
});
