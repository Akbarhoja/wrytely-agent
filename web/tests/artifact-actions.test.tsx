import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ArtifactActions } from "../components/artifact-actions";

const id = "00000000-0000-4000-8000-000000000001";

it("recovers controls after access loss without replaying an aborted action", async () => {
  let finish: (response: Response) => void = () => {};
  const fetch = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve;
        }),
    )
    .mockResolvedValue(Response.json({ id, state: "ready" }));
  vi.stubGlobal("fetch", fetch);
  const props = { artifactId: id, onSessionExpired: vi.fn() };
  const view = render(<ArtifactActions {...props} enabled />);
  fireEvent.click(screen.getByText("Send this file to my WhatsApp"));
  expect(fetch).toHaveBeenCalledTimes(1);
  view.rerender(<ArtifactActions {...props} enabled={false} />);
  expect(
    screen.getByRole<HTMLButtonElement>("button", { name: "Send this file to my WhatsApp" })
      .disabled,
  ).toBe(true);
  const signal = (fetch.mock.calls[0][1] as RequestInit).signal;
  expect(signal?.aborted).toBe(true);
  view.rerender(<ArtifactActions {...props} enabled />);
  finish(Response.json({ id, state: "ready" }));
  await waitFor(() =>
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: "Send this file to my WhatsApp" })
        .disabled,
    ).toBe(false),
  );
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(
    screen.queryByText("File delivery requested. Phone delivery has not been confirmed."),
  ).toBeNull();
  fireEvent.click(screen.getByText("Send this file to my WhatsApp"));
  await screen.findByText("File delivery requested. Phone delivery has not been confirmed.");
  expect(fetch).toHaveBeenCalledTimes(2);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("clears private revision instructions when an expired session returns HTML", async () => {
  const expired = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("<html>Expired</html>", { status: 401 })),
  );
  render(<ArtifactActions artifactId={id} enabled onSessionExpired={expired} />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Private revision feedback" } });
  fireEvent.click(screen.getByText("Request a revision"));
  await waitFor(() => expect(expired).toHaveBeenCalledOnce());
  expect(screen.getByRole<HTMLTextAreaElement>("textbox").value).toBe("");
  expect(
    screen.getByRole<HTMLButtonElement>("button", { name: "Request a revision" }).disabled,
  ).toBe(true);
});

it("retains the same revision key after an uncertain response and does not send on render", async () => {
  let first = true;
  const fetch = vi.fn(async () => {
    if (first) {
      first = false;
      throw Error("Response lost");
    }
    return Response.json({ task_id: id });
  });
  vi.stubGlobal("fetch", fetch);
  render(<ArtifactActions artifactId={id} enabled onSessionExpired={() => {}} />);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Clarify the argument" } });
  fireEvent.click(screen.getByText("Request a revision"));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByText("Request a revision"));
  await screen.findByText(/Revision requested/);
  expect(fetch).toHaveBeenCalledTimes(2);
  const calls = fetch.mock.calls as unknown as [string, RequestInit][];
  expect(calls[0][1].body).toBe(calls[1][1].body);
});

it("queues a file only after the explicit button and does not claim phone delivery", async () => {
  const fetch = vi.fn(async () => Response.json({ id, state: "ready" }));
  vi.stubGlobal("fetch", fetch);
  render(<ArtifactActions artifactId={id} enabled onSessionExpired={() => {}} />);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Send this file to my WhatsApp"));
  await screen.findByText("File delivery requested. Phone delivery has not been confirmed.");
  const calls = fetch.mock.calls as unknown as [string, RequestInit][];
  expect(calls[0][0]).toBe(`/api/agent/v2/artifacts/${id}/delivery`);
  expect(calls[0][1].body).toBeUndefined();
});

it("fences private actions and removes instructions after session expiry", async () => {
  const expired = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({}, { status: 401 })),
  );
  render(<ArtifactActions artifactId={id} enabled onSessionExpired={expired} />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Private revision" } });
  fireEvent.click(screen.getByText("Download Word file"));
  await waitFor(() => expect(expired).toHaveBeenCalledOnce());
  expect(screen.getByRole<HTMLTextAreaElement>("textbox").value).toBe("");
  expect(
    screen.getByRole<HTMLButtonElement>("button", { name: "Download Word file" }).disabled,
  ).toBe(true);
});

it("clears prior-artifact instructions and disabled controls never dispatch", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  const view = render(<ArtifactActions artifactId={id} enabled onSessionExpired={() => {}} />);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Old private text" } });
  view.rerender(
    <ArtifactActions
      artifactId={id.replace(/1$/, "2")}
      enabled={false}
      onSessionExpired={() => {}}
    />,
  );
  expect(screen.getByRole<HTMLTextAreaElement>("textbox").value).toBe("");
  fireEvent.click(screen.getByText("Download Word file"));
  expect(fetch).not.toHaveBeenCalled();
});
