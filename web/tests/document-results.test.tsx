import { afterEach, it, expect, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { DocumentResults } from "../components/document-results";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const id = "00000000-0000-4000-8000-000000000001";
it("opens escaped document draft, paginates exact original, and clears content after revoked authority", async () => {
  let blocked = false;
  const fetch = vi.fn(async (url: unknown) => {
    const path = String(url);
    if (blocked)
      return Response.json({ detail: { code: "source_refresh_required" } }, { status: 409 });
    if (path.includes("/evidence/"))
      return Response.json({
        schema_version: 2,
        artifact_id: id,
        group: "citation",
        index: 0,
        quote_matches: true,
        reference: { kind: "canvas_document", quote: "exact quote" },
        source: {
          kind: "canvas_document",
          sections: [{ slot: 0, page: 1, text: "Original text <script>not executable</script>" }],
          next_slot: 1,
          missing: ["image_text_unread"],
        },
        evidence_status: { state: "incomplete", reasons: [] },
      });
    if (path.includes("/responsibilities/"))
      return Response.json({
        schema_version: 2,
        artifacts: [
          { id, created_at: "2026-11-02T01:00:00Z", saved_state: "ready", memory_stale: false },
        ],
        next: null,
      });
    return Response.json({
      schema_version: 2,
      artifact: {
        id,
        responsibility_id: id,
        memory_stale: false,
        draft: {
          title: "Synthetic draft",
          body: "<script>private draft</script>",
          disclosure: "Review me",
          citations: [
            { claim: "Claim", evidence: { kind: "canvas_document", quote: "exact quote" } },
          ],
        },
      },
      controls: { agent_paused: true, responsibility_status: "active" },
      latest_check: null,
      evidence_status: { state: "incomplete", reasons: ["item_incomplete"] },
      limits: "Inspection is not submission permission.",
    });
  });
  vi.stubGlobal("fetch", fetch);
  const view = render(
    <DocumentResults responsibilityId={id} enabled onSessionExpired={() => {}} />,
  );
  fireEvent.click(await screen.findByRole("button", { name: /Saved .*Inspect checks/ }));
  await screen.findByText("<script>private draft</script>");
  expect(view.container.querySelector("script")).toBeNull();
  fireEvent.click(screen.getByText("Read original source 1"));
  await screen.findByText("Original text <script>not executable</script>");
  blocked = true;
  fireEvent.click(screen.getByText("Next original section"));
  await screen.findByText(/Source access changed/);
  expect(screen.queryByText("<script>private draft</script>")).toBeNull();
  expect(screen.queryByText("Original text <script>not executable</script>")).toBeNull();
  expect(String(fetch.mock.calls.at(-1)![0])).toContain("first_slot=1");
});
it("disabled view does not fetch or retain results", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  render(<DocumentResults responsibilityId={id} enabled={false} onSessionExpired={() => {}} />);
  expect(fetch).not.toHaveBeenCalled();
});
