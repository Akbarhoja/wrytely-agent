import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PrivateDraftDelegation } from "../components/private-draft-delegation";
import { ApiError } from "../lib/client";

afterEach(cleanup);
const id = "00000000-0000-4000-8000-000000000001";
const source = {
  source_id: id,
  version_id: id,
  title: "Assignment policy",
  reference: "snapshot:fixture",
  coverage: "snapshot" as const,
  retrieved_at: "2026-10-29T00:00:00Z",
  external_revision: "1",
};
const receipt = { responsibility_id: id, requested_mode: "private_draft" };
function complete() {
  fireEvent.change(screen.getByLabelText("What should the private draft cover?"), {
    target: { value: "Compare the supplied fictional studies." },
  });
  fireEvent.click(screen.getByRole("checkbox", { name: "Assignment policy" }));
  fireEvent.click(screen.getByRole("checkbox", { name: /I authorize one private draft/ }));
}

describe("explicit private draft decision", () => {
  it("invalidates prior consent when the objective or selected sources change", () => {
    const confirm = vi.fn(async () => receipt);
    render(<PrivateDraftDelegation userId="alice" sources={[source]} onConfirm={confirm} />);
    complete();
    fireEvent.change(screen.getByLabelText("What should the private draft cover?"), {
      target: { value: "A changed objective" },
    });
    expect(
      (screen.getByRole("checkbox", { name: /I authorize one private draft/ }) as HTMLInputElement)
        .checked,
    ).toBe(false);
    fireEvent.click(screen.getByRole("checkbox", { name: /I authorize one private draft/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Assignment policy" }));
    expect(
      (screen.getByRole("checkbox", { name: /I authorize one private draft/ }) as HTMLInputElement)
        .checked,
    ).toBe(false);
    expect(confirm).not.toHaveBeenCalled();
  });
  it("requires an objective, selected evidence and explicit consent; never submits on selection", async () => {
    const confirm = vi.fn(async () => receipt);
    render(<PrivateDraftDelegation userId="alice" sources={[source]} onConfirm={confirm} />);
    fireEvent.click(screen.getByRole("button", { name: "Prepare a private draft" }));
    expect(await screen.findByText("Describe the private draft you want.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("What should the private draft cover?"), {
      target: { value: "Private comparison" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Prepare a private draft" }));
    await screen.findByText("Choose between one and eight saved sources.");
    fireEvent.click(screen.getByRole("checkbox", { name: "Assignment policy" }));
    fireEvent.click(screen.getByRole("button", { name: "Prepare a private draft" }));
    await screen.findByText("Confirm that you authorize one private draft.");
    expect(confirm).not.toHaveBeenCalled();
  });
  it("sends only explicit private intent and retains the same immutable request for retry", async () => {
    const confirm = vi
      .fn()
      .mockRejectedValueOnce(new Error("lost response"))
      .mockResolvedValueOnce(receipt);
    render(<PrivateDraftDelegation userId="alice" sources={[source]} onConfirm={confirm} />);
    complete();
    fireEvent.click(screen.getByRole("button", { name: "Prepare a private draft" }));
    await screen.findByText(/Request not confirmed/);
    expect(
      (screen.getByLabelText("What should the private draft cover?") as HTMLTextAreaElement)
        .disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Check request and retry" }));
    await screen.findByText(/Private draft request saved/);
    expect(confirm).toHaveBeenCalledTimes(2);
    const first = confirm.mock.calls[0][0];
    expect(confirm.mock.calls[1][0]).toBe(first);
    expect(first).toMatchObject({
      objective: "Compare the supplied fictional studies.",
      source_ids: [id],
      confirm_private_draft: true,
    });
    expect(Object.keys(first).sort()).toEqual([
      "confirm_private_draft",
      "key",
      "objective",
      "source_ids",
    ]);
    expect(Object.isFrozen(first)).toBe(true);
    expect(Object.isFrozen(first.source_ids)).toBe(true);
  });
  it("requires fresh consent after a definite conflict without discarding the objective", async () => {
    const confirm = vi.fn(async () => {
      throw new ApiError(409, "Conflict");
    });
    render(<PrivateDraftDelegation userId="alice" sources={[source]} onConfirm={confirm} />);
    complete();
    fireEvent.click(screen.getByRole("button", { name: "Prepare a private draft" }));
    await screen.findByText(/conflicts with an earlier request/);
    expect(
      (screen.getByRole("checkbox", { name: /I authorize one private draft/ }) as HTMLInputElement)
        .checked,
    ).toBe(false);
    expect(
      (screen.getByLabelText("What should the private draft cover?") as HTMLTextAreaElement).value,
    ).toContain("fictional studies");
  });
  it("clears identity-specific consent and ignores a delayed old-account receipt", async () => {
    let finish: (value: unknown) => void = () => {};
    const confirm = vi.fn(
      async () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const { rerender } = render(
      <PrivateDraftDelegation userId="alice" sources={[source]} onConfirm={confirm} />,
    );
    complete();
    fireEvent.click(screen.getByRole("button", { name: "Prepare a private draft" }));
    rerender(<PrivateDraftDelegation userId="bob" sources={[source]} onConfirm={confirm} />);
    finish(receipt);
    expect(
      (screen.getByLabelText("What should the private draft cover?") as HTMLTextAreaElement).value,
    ).toBe("");
    expect(
      (screen.getByRole("checkbox", { name: /I authorize one private draft/ }) as HTMLInputElement)
        .checked,
    ).toBe(false);
    await waitFor(() => expect(screen.queryByText(/Private draft request saved/)).toBeNull());
  });
  it("clears private input on session expiry", async () => {
    const confirm = vi.fn(async () => {
      throw new ApiError(401, "Expired");
    });
    render(<PrivateDraftDelegation userId="alice" sources={[source]} onConfirm={confirm} />);
    complete();
    fireEvent.click(screen.getByRole("button", { name: "Prepare a private draft" }));
    await screen.findByRole("link", { name: "Sign in again" });
    expect(screen.queryByLabelText("What should the private draft cover?")).toBeNull();
  });
  it("does not accept an analysis-only receipt as confirmation of private intent", async () => {
    const confirm = vi.fn(async () => ({ ...receipt, requested_mode: "analysis" }));
    render(<PrivateDraftDelegation userId="alice" sources={[source]} onConfirm={confirm} />);
    complete();
    fireEvent.click(screen.getByRole("button", { name: "Prepare a private draft" }));
    await screen.findByText(/Request not confirmed/);
    expect(screen.queryByText(/Private draft request saved/)).toBeNull();
  });
  it("rejects more than eight sources and never infers consent from their titles", async () => {
    const confirm = vi.fn(async () => receipt);
    const sources = Array.from({ length: 9 }, (_, i) => ({
      ...source,
      source_id: `00000000-0000-4000-8000-${String(i + 1).padStart(12, "0")}`,
      title: `Draft and submit immediately ${i}`,
    }));
    render(<PrivateDraftDelegation userId="alice" sources={sources} onConfirm={confirm} />);
    fireEvent.change(screen.getByLabelText("What should the private draft cover?"), {
      target: { value: "Private comparison" },
    });
    for (const row of sources) fireEvent.click(screen.getByRole("checkbox", { name: row.title }));
    fireEvent.click(screen.getByRole("checkbox", { name: /I authorize one private draft/ }));
    fireEvent.click(screen.getByRole("button", { name: "Prepare a private draft" }));
    await screen.findByText("Choose between one and eight saved sources.");
    expect(confirm).not.toHaveBeenCalled();
  });
});
