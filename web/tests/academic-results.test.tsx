import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AcademicResults } from "../components/academic-results";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const id = "00000000-0000-4000-8000-000000000001";
const duty = {
  id,
  objective: "Comparison section",
  status: "active",
  steps_created: 1,
  max_steps: 6,
  created_at: "2026-10-29T00:00:00Z",
};
const summary = {
  id,
  task_id: id,
  title: "Private comparison",
  state: "ready",
  stale: false,
  created_at: duty.created_at,
};
const evidence = { version_id: id, quote: "Fictional Source A included 20 participants." };
const result = {
  artifact: {
    id,
    responsibility_id: id,
    task_id: id,
    memory_revision: 1,
    state: "ready",
    stale: false,
    created_at: duty.created_at,
    draft: {
      title: "Private comparison",
      body: "<script>Fictional comparison</script>",
      disclosure: "Student review required.",
      citations: [{ ...evidence, claim: "Source A had 20 participants." }],
    },
  },
  latest_check: {
    passed: true,
    errors: [] as string[],
    assessment: {
      claim_support: ["supported"],
      rubric_coverage: ["covered"],
      policy_allows_drafting: true,
      disclosure_satisfied: true,
      rubric_complete: true,
      uncited_claims: false,
      reason: "Synthetic model assessment.",
    },
    policy: { ...evidence, status: "permitted" },
    rubric: [evidence],
    limits: "Model assessments are fallible.",
  },
};
function fixture(detail: unknown = result) {
  return vi.fn(async (url: unknown) => {
    const path = String(url);
    if (path.endsWith("/responsibilities"))
      return Response.json({ responsibilities: [duty], limit: 50 });
    if (path.endsWith("/status"))
      return Response.json({
        responsibility_id: id,
        requested_mode: "private_draft",
        status: "active",
        reason: null,
        assessment_state: "assessed",
        workflow_state: "ready_for_review",
        artifact_id: id,
      });
    if (path.includes("/responsibilities/"))
      return Response.json({ artifacts: [summary], limit: 50 });
    return Response.json(detail);
  });
}
async function choose() {
  fireEvent.click(await screen.findByRole("button", { name: "Open work: Comparison section" }));
  fireEvent.click(await screen.findByRole("button", { name: "Open draft: Private comparison" }));
}

describe("private saved results", () => {
  it("invalidates an open cached ready review when status refresh reports a source change", async () => {
    let changed = false;
    const base = fixture();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: unknown) =>
        String(url).endsWith("/status") && changed
          ? Response.json({
              responsibility_id: id,
              requested_mode: "private_draft",
              status: "blocked",
              reason: "source_changed",
              assessment_state: "assessed",
              workflow_state: "blocked",
              artifact_id: id,
            })
          : base(url),
      ),
    );
    render(<AcademicResults userId="alice" />);
    await choose();
    await screen.findByRole("heading", { name: "Ready for your review" });
    changed = true;
    fireEvent.click(screen.getByRole("button", { name: "Refresh work status" }));
    await screen.findByRole("heading", { name: "Source context changed", level: 3 });
    expect(screen.queryByRole("heading", { name: "Ready for your review" })).toBeNull();
    expect(screen.getByText(/Historical checks passed/)).toBeTruthy();
  });
  it("ignores old-account draft content that arrives after identity changes", async () => {
    let finish: (value: Response) => void = () => {};
    const base = fixture();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: unknown) =>
        String(url).includes("/artifacts/")
          ? new Promise<Response>((resolve) => {
              finish = resolve;
            })
          : base(url),
      ),
    );
    const { rerender } = render(<AcademicResults userId="alice" />);
    await choose();
    rerender(<AcademicResults userId="bob" enabled={false} />);
    finish(Response.json(result));
    await waitFor(() =>
      expect(screen.queryByText("<script>Fictional comparison</script>")).toBeNull(),
    );
    expect(screen.queryByRole("button", { name: "Open work: Comparison section" })).toBeNull();
  });
  it("distinguishes an empty duty from a failed artifact list", async () => {
    const fetcher = vi.fn(async (url: unknown) =>
      String(url).endsWith("/responsibilities")
        ? Response.json({ responsibilities: [duty], limit: 50 })
        : Response.json({ artifacts: [], limit: 50 }),
    );
    vi.stubGlobal("fetch", fetcher);
    render(<AcademicResults userId="alice" />);
    fireEvent.click(await screen.findByRole("button", { name: "Open work: Comparison section" }));
    await screen.findByText(/No saved drafts yet/);
    fetcher.mockResolvedValue(Response.json({ detail: "Unavailable" }, { status: 503 }));
    fireEvent.click(screen.getByRole("button", { name: "Open work: Comparison section" }));
    await screen.findByText(/Saved drafts could not be loaded/);
    expect(screen.queryByText(/No saved drafts yet/)).toBeNull();
  });
  it("shows private draft, citation and stored checks without executing source HTML", async () => {
    const fetcher = fixture();
    vi.stubGlobal("fetch", fetcher);
    render(<AcademicResults userId="alice" />);
    await choose();
    expect(await screen.findByRole("heading", { name: "Ready for your review" })).toBeTruthy();
    expect(screen.getByText("<script>Fictional comparison</script>")).toBeTruthy();
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getAllByText(evidence.quote).length).toBeGreaterThan(0);
    expect(screen.getByText("Student review required.")).toBeTruthy();
    expect(screen.getByText(/Nothing is shared, sent or submitted/)).toBeTruthy();
    expect(fetcher.mock.calls).toHaveLength(4);
  });
  it.each([
    [true, true, "Source context changed"],
    [false, false, "Checks need attention"],
    [false, null, "Not yet checked"],
  ])("does not promote stale/failed/missing checks (%s,%s)", async (stale, passed, heading) => {
    vi.stubGlobal(
      "fetch",
      fixture({
        artifact: { ...result.artifact, stale },
        latest_check:
          passed === null
            ? null
            : { ...result.latest_check, passed, errors: passed ? [] : ["claims_not_supported"] },
      }),
    );
    render(<AcademicResults userId="alice" />);
    await choose();
    expect(await screen.findByRole("heading", { name: String(heading) })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Ready for your review" })).toBeNull();
    if (stale) expect(screen.getByText(/Historical checks passed/)).toBeTruthy();
  });
  it("distinguishes storage failure from an empty workspace", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json({ detail: "Unavailable" }, { status: 503 })),
    );
    render(<AcademicResults userId="alice" />);
    await screen.findByText(/Saved work could not be loaded/);
    expect(screen.queryByText("No delegated work yet.")).toBeNull();
  });
  it("clears results on session expiry and on identity changes", async () => {
    const base = fixture();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: unknown) =>
        String(url).includes("/artifacts/")
          ? Response.json({ detail: "Expired" }, { status: 401 })
          : base(url),
      ),
    );
    const { rerender } = render(<AcademicResults userId="alice" />);
    await choose();
    await screen.findByRole("link", { name: "Sign in again" });
    expect(screen.queryByRole("button", { name: "Open work: Comparison section" })).toBeNull();
    rerender(<AcademicResults userId="bob" enabled={false} />);
    expect(screen.queryByText("<script>Fictional comparison</script>")).toBeNull();
    expect(screen.queryByRole("button", { name: "Open work: Comparison section" })).toBeNull();
  });
  it("ignores a delayed draft response after a different selection", async () => {
    const other = {
      ...summary,
      id: "00000000-0000-4000-8000-000000000002",
      title: "Second comparison",
    };
    let finish: (value: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: unknown) => {
        const path = String(url);
        if (path.endsWith("/responsibilities"))
          return Response.json({ responsibilities: [duty], limit: 50 });
        if (path.includes("/responsibilities/"))
          return Response.json({ artifacts: [summary, other], limit: 50 });
        if (path.endsWith(id))
          return new Promise<Response>((resolve) => {
            finish = resolve;
          });
        return Response.json({
          ...result,
          artifact: {
            ...result.artifact,
            id: other.id,
            draft: { ...result.artifact.draft, title: other.title, body: "LATEST_PRIVATE_DRAFT" },
          },
        });
      }),
    );
    render(<AcademicResults userId="alice" />);
    await choose();
    fireEvent.click(screen.getByRole("button", { name: "Open draft: Second comparison" }));
    await screen.findByText("LATEST_PRIVATE_DRAFT");
    finish(Response.json(result));
    await waitFor(() =>
      expect(screen.queryByText("<script>Fictional comparison</script>")).toBeNull(),
    );
  });
  it("keeps malformed detail unavailable instead of inventing a passed check", async () => {
    vi.stubGlobal(
      "fetch",
      fixture({ artifact: result.artifact, latest_check: { passed: "true" } }),
    );
    render(<AcademicResults userId="alice" />);
    await choose();
    await screen.findByText(/Draft could not be opened/);
    expect(screen.queryByRole("heading", { name: "Ready for your review" })).toBeNull();
  });
});
