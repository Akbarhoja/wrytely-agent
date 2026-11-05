import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AcademicContext } from "../components/academic-context";
import { PrivateDraftStatus } from "../components/private-draft-status";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const id = "00000000-0000-4000-8000-000000000001";
const other = "00000000-0000-4000-8000-000000000002";
const snapshot = {
  source_id: id,
  version_id: id,
  title: "Fictional assignment",
  reference: "snapshot:demo",
  coverage: "snapshot",
  retrieved_at: "2026-10-29T00:00:00Z",
  external_revision: "1",
  content: "Fictional evidence only.",
};
const status = {
  responsibility_id: id,
  requested_mode: "private_draft",
  status: "active",
  reason: null,
  assessment_state: "pending",
  workflow_state: "pending",
  artifact_id: null,
};
function decide() {
  fireEvent.change(screen.getByLabelText("What should the private draft cover?"), {
    target: { value: "Compare the fictional studies." },
  });
  fireEvent.click(screen.getByRole("checkbox", { name: snapshot.title }));
  fireEvent.click(screen.getByRole("checkbox", { name: /I authorize one private draft/ }));
  fireEvent.click(screen.getByRole("button", { name: "Prepare a private draft" }));
}

describe("connected private draft flow", () => {
  it("uses the saved source list, explicit same-key retry and read-only status refresh", async () => {
    let attempts = 0;
    let complete = false;
    const fetcher = vi.fn(async (url: unknown, options?: RequestInit) => {
      if (String(url).endsWith("/sources"))
        return Response.json({ sources: [snapshot], limit: 50 });
      if (options?.method === "POST") {
        if (++attempts === 1) throw new Error("Synthetic lost receipt");
        return Response.json(
          { responsibility_id: id, requested_mode: "private_draft" },
          { status: 201 },
        );
      }
      return Response.json(
        complete
          ? {
              ...status,
              assessment_state: "assessed",
              workflow_state: "ready_for_review",
              artifact_id: other,
            }
          : status,
      );
    });
    vi.stubGlobal("fetch", fetcher);
    const viewResults = vi.fn();
    render(<AcademicContext userId="alice" onViewResults={viewResults} />);
    await screen.findByRole("checkbox", { name: snapshot.title });
    expect(fetcher).toHaveBeenCalledTimes(1);
    decide();
    await screen.findByText(/Request not confirmed/);
    const first = fetcher.mock.calls.find(([, o]) => o?.method === "POST")![1]!;
    expect(JSON.parse(String(first.body))).toEqual({
      objective: "Compare the fictional studies.",
      source_ids: [id],
      confirm_private_draft: true,
    });
    expect(Object.keys(JSON.parse(String(first.body)))).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "Check request and retry" }));
    await screen.findByRole("heading", { name: "Waiting for policy and requirements checks" });
    const posts = fetcher.mock.calls.filter(([, o]) => o?.method === "POST");
    expect(posts).toHaveLength(2);
    expect(posts[1][1]?.body).toBe(first.body);
    expect(posts[1][1]?.headers).toEqual(first.headers);
    expect(new Headers(first.headers).get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    complete = true;
    fireEvent.click(screen.getByRole("button", { name: "Refresh work status" }));
    await screen.findByRole("heading", { name: "Draft ready for your review" });
    expect(fetcher.mock.calls.filter(([, o]) => o?.method === "POST")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "View private results" }));
    expect(viewResults).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Status does not authorize sharing/)).toBeTruthy();
  });

  it("clears all context and decision input when the status session expires", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: unknown, options?: RequestInit) => {
        if (String(url).endsWith("/sources"))
          return Response.json({ sources: [snapshot], limit: 50 });
        if (options?.method === "POST")
          return Response.json({ responsibility_id: id, requested_mode: "private_draft" });
        return Response.json({ detail: "Expired" }, { status: 401 });
      }),
    );
    render(<AcademicContext userId="alice" />);
    await screen.findByRole("checkbox", { name: snapshot.title });
    fireEvent.change(screen.getByLabelText("Pasted text"), {
      target: { value: "Unsaved private text" },
    });
    decide();
    await screen.findByRole("link", { name: "Sign in again" });
    expect(screen.queryByLabelText("Pasted text")).toBeNull();
    expect(screen.queryByLabelText("What should the private draft cover?")).toBeNull();
    expect(screen.queryByText(/Private draft request saved/)).toBeNull();
  });

  it("ignores an old-account creation receipt after identity changes", async () => {
    let finish: (response: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: unknown, options?: RequestInit) => {
        if (options?.method === "POST")
          return new Promise<Response>((resolve) => {
            finish = resolve;
          });
        return Response.json({ sources: [snapshot], limit: 50 });
      }),
    );
    const { rerender } = render(<AcademicContext userId="alice" />);
    await screen.findByRole("checkbox", { name: snapshot.title });
    decide();
    rerender(<AcademicContext userId="bob" enabled={false} />);
    finish(Response.json({ responsibility_id: id, requested_mode: "private_draft" }));
    await waitFor(() => expect(screen.queryByText(/Private draft request saved/)).toBeNull());
    expect(
      (screen.getByLabelText("What should the private draft cover?") as HTMLTextAreaElement).value,
    ).toBe("");
  });

  it.each([404, 429])(
    "allows review and fresh consent after definite rejection %s",
    async (statusCode) => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async (_url: unknown, options?: RequestInit) =>
          options?.method === "POST"
            ? Response.json({ detail: "Unavailable" }, { status: statusCode })
            : Response.json({ sources: [snapshot], limit: 50 }),
        ),
      );
      render(<AcademicContext userId="alice" />);
      await screen.findByRole("checkbox", { name: snapshot.title });
      decide();
      await screen.findByText(/request was rejected/i);
      expect(
        (screen.getByLabelText("What should the private draft cover?") as HTMLTextAreaElement)
          .disabled,
      ).toBe(false);
      expect(
        (
          screen.getByRole("checkbox", {
            name: /I authorize one private draft/,
          }) as HTMLInputElement
        ).checked,
      ).toBe(false);
    },
  );

  it("gives source-change blocking precedence over a historical assessed/ready status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({
          ...status,
          status: "blocked",
          reason: "source_changed",
          assessment_state: "assessed",
          workflow_state: "ready_for_review",
          artifact_id: other,
        }),
      ),
    );
    render(<PrivateDraftStatus responsibilityId={id} />);
    await screen.findByRole("heading", { name: "Source context changed" });
    expect(screen.queryByRole("heading", { name: "Draft ready for your review" })).toBeNull();
  });

  it.each([
    { ...status, responsibility_id: other },
    { ...status, reason: "<script>untrusted reason</script>" },
    { ...status, workflow_state: "submitted" },
  ])("rejects mismatched or unrecognized status instead of guessing readiness", async (value) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json(value)),
    );
    render(<PrivateDraftStatus responsibilityId={id} />);
    await screen.findByText(/Work status could not be loaded/);
    expect(screen.queryByText(/untrusted reason/)).toBeNull();
  });

  it("fences delayed status from an older duty selection", async () => {
    let finish: (response: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: unknown) =>
        String(url).includes(id)
          ? new Promise<Response>((resolve) => {
              finish = resolve;
            })
          : Response.json({
              ...status,
              responsibility_id: other,
              status: "blocked",
              reason: "draft_policy_or_rubric_blocked",
              assessment_state: "blocked",
              workflow_state: "blocked",
            }),
      ),
    );
    const { rerender } = render(<PrivateDraftStatus responsibilityId={id} />);
    rerender(<PrivateDraftStatus responsibilityId={other} />);
    await screen.findByRole("heading", { name: "Policy or requirements need attention" });
    finish(
      Response.json({
        ...status,
        workflow_state: "ready_for_review",
        assessment_state: "assessed",
        artifact_id: other,
      }),
    );
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Draft ready for your review" })).toBeNull(),
    );
  });
});
