import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AcademicContext } from "../components/academic-context";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
const id = "00000000-0000-4000-8000-000000000001";
const source = {
  source_id: id,
  version_id: id,
  title: "Fictional rubric",
  reference: "snapshot:fixture",
  coverage: "snapshot",
  retrieved_at: "2026-10-29T00:00:00Z",
  external_revision: "1",
};
function fill() {
  fireEvent.change(screen.getByLabelText("Snapshot title"), {
    target: { value: "Fictional rubric" },
  });
  fireEvent.change(screen.getByLabelText("Pasted text"), {
    target: { value: "Private synthetic text" },
  });
}

describe("private academic snapshots", () => {
  it("allows correction after a definite conflict instead of trapping an endless retry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: unknown, options?: RequestInit) =>
        options?.method === "POST"
          ? Response.json({ detail: "Snapshot request changed" }, { status: 409 })
          : Response.json({ sources: [], limit: 50 }),
      ),
    );
    render(<AcademicContext userId="alice" />);
    await screen.findByText("No saved snapshots yet.");
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Save snapshot" }));
    await screen.findByText(/conflicts with an earlier snapshot/);
    expect((screen.getByLabelText("Pasted text") as HTMLTextAreaElement).disabled).toBe(false);
    expect((screen.getByLabelText("Pasted text") as HTMLTextAreaElement).value).toBe(
      "Private synthetic text",
    );
  });
  it("does not replace a later selected detail with a delayed older response", async () => {
    const other = {
      ...source,
      source_id: "00000000-0000-4000-8000-000000000002",
      title: "Second source",
    };
    let finish: (response: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: unknown) => {
        if (String(url).endsWith(id))
          return new Promise<Response>((resolve) => {
            finish = resolve;
          });
        if (String(url).endsWith(other.source_id))
          return Response.json({ ...other, content: "LATEST_SELECTION" });
        return Response.json({ sources: [source, other], limit: 50 });
      }),
    );
    render(<AcademicContext userId="alice" />);
    fireEvent.click(await screen.findByRole("button", { name: "Open Fictional rubric" }));
    fireEvent.click(screen.getByRole("button", { name: "Open Second source" }));
    await screen.findByText("LATEST_SELECTION");
    finish(Response.json({ ...source, content: "OLD_SELECTION" }));
    await waitFor(() => expect(screen.queryByText("OLD_SELECTION")).toBeNull());
    expect(screen.getByText("LATEST_SELECTION")).toBeTruthy();
  });
  it("rejects oversized UTF-8 text locally before sending", async () => {
    const fetcher = vi.fn(async () => Response.json({ sources: [], limit: 50 }));
    vi.stubGlobal("fetch", fetcher);
    render(<AcademicContext userId="alice" />);
    await screen.findByText("No saved snapshots yet.");
    fill();
    fireEvent.change(screen.getByLabelText("Pasted text"), {
      target: { value: "字".repeat(23000) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save snapshot" }));
    await screen.findByText(/This snapshot is too long/);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("loads saved text only on request and never renders source HTML", async () => {
    const fetcher = vi.fn(async (url: unknown) =>
      Response.json(
        String(url).endsWith(id)
          ? { ...source, content: "<script>untrusted evidence</script>" }
          : { sources: [source], limit: 50 },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    render(<AcademicContext userId="alice" />);
    fireEvent.click(await screen.findByRole("button", { name: "Open Fictional rubric" }));
    expect(await screen.findByText("<script>untrusted evidence</script>")).toBeTruthy();
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getByText(/does not monitor later changes/)).toBeTruthy();
    expect(fetcher.mock.calls.every(([url]) => String(url).includes("/sources"))).toBe(true);
  });
  it("retains uncertain text and uses the exact same key/payload for explicit retry", async () => {
    const writes: RequestInit[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: unknown, options?: RequestInit) => {
        if (options?.method === "POST") {
          writes.push(options);
          if (writes.length === 1) throw new Error("lost response");
          return Response.json({ ...source, content: "Private synthetic text" }, { status: 201 });
        }
        return Response.json({ sources: [], limit: 50 });
      }),
    );
    render(<AcademicContext userId="alice" />);
    await screen.findByText("No saved snapshots yet.");
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Save snapshot" }));
    await screen.findByText(/Save not confirmed/);
    expect((screen.getByLabelText("Pasted text") as HTMLTextAreaElement).value).toBe(
      "Private synthetic text",
    );
    expect((screen.getByLabelText("Pasted text") as HTMLTextAreaElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Check and retry save" }));
    await screen.findByText("Snapshot saved. No work has started.");
    expect(document.activeElement).toBe(screen.getByLabelText("Snapshot title"));
    expect(writes).toHaveLength(2);
    expect(writes[0].body).toBe(writes[1].body);
    expect(new Headers(writes[0].headers).get("Idempotency-Key")).toBe(
      new Headers(writes[1].headers).get("Idempotency-Key"),
    );
    expect((screen.getByLabelText("Pasted text") as HTMLTextAreaElement).value).toBe("");
  });
  it("clears private draft/results immediately across identities and ignores late responses", async () => {
    let finish: (response: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Promise<Response>((resolve) => {
            finish = resolve;
          }),
      ),
    );
    const { rerender } = render(<AcademicContext userId="alice" />);
    fill();
    rerender(<AcademicContext userId="bob" enabled={false} />);
    finish(Response.json({ sources: [source], limit: 50 }));
    expect((screen.getByLabelText("Pasted text") as HTMLTextAreaElement).value).toBe("");
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Open Fictional rubric" })).toBeNull(),
    );
  });
  it("clears private state after session expiry and offers sign-in", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: unknown, options?: RequestInit) =>
        options?.method === "POST"
          ? Response.json({ detail: "Session expired" }, { status: 401 })
          : Response.json({ sources: [source], limit: 50 }),
      ),
    );
    render(<AcademicContext userId="alice" />);
    await screen.findByRole("button", { name: "Open Fictional rubric" });
    fill();
    fireEvent.click(screen.getByRole("button", { name: "Save snapshot" }));
    await screen.findByRole("link", { name: "Sign in again" });
    expect(screen.queryByLabelText("Pasted text")).toBeNull();
    expect(screen.queryByRole("button", { name: "Open Fictional rubric" })).toBeNull();
  });
  it("shows storage errors honestly and validates empty fields before saving", async () => {
    const fetcher = vi.fn(async () => Response.json({ detail: "Unavailable" }, { status: 503 }));
    vi.stubGlobal("fetch", fetcher);
    render(<AcademicContext userId="alice" />);
    await screen.findByText(/Saved snapshots could not be loaded/);
    expect(screen.queryByText("No saved snapshots yet.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Save snapshot" }));
    expect(await screen.findByText("Add a title and some text before saving.")).toBeTruthy();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
