import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CourseSupervision } from "../components/course-supervision";
import { preparation } from "./preparation-fixture";

const id = "00000000-0000-4000-8000-000000000001";
const offer = "00000000-0000-4000-8000-000000000002";
const props = {
  userId: "user_alice",
  connectionId: id,
  courseId: "101",
  title: "Synthetic course",
  enabled: true,
  selected: true,
};
const monitor = () => ({
  id,
  state: "ready",
  next_check_at: null,
  calls_reserved: 0,
  call_limit: 6,
  notification_consent: false,
  reason: null,
  offers: [
    {
      id: offer,
      message: "Prepare a study draft?",
      reason: "Based on the current assignment",
      state: "pending",
    },
  ],
});
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

it.each(["access", "session", "account", "malformed"])(
  "clears preparation on %s change",
  async (mode) => {
    const p = preparation();
    let changed = false;
    const expired = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: unknown) => {
        if (changed && mode === "session") return Response.json({}, { status: 401 });
        const value = {
          ...monitor(),
          offers: [],
          preparations: [changed && mode === "malformed" ? { ...p, current: "yes" } : p],
        };
        return Response.json(
          String(url).includes("?connection_id=")
            ? { supervision: changed && mode === "account" ? null : value }
            : value,
        );
      }),
    );
    const view = render(<CourseSupervision {...props} onSessionExpired={expired} />);
    await screen.findByText(p.title);
    expect(screen.queryByRole("button", { name: /accept|download|send this/i })).toBeNull();
    changed = true;
    if (mode === "access") view.rerender(<CourseSupervision {...props} enabled={false} />);
    else if (mode === "account") view.rerender(<CourseSupervision {...props} userId="user_bob" />);
    else fireEvent.click(screen.getByText("Refresh supervision"));
    await waitFor(() => expect(screen.queryByText(p.title)).toBeNull());
    if (mode === "session") await waitFor(() => expect(expired).toHaveBeenCalledOnce());
    if (mode === "malformed") await screen.findByRole("alert");
  },
);

it("requires explicit enable, consent and acceptance; displays saved state", async () => {
  const value = monitor();
  const fetch = vi.fn(async (url: unknown, options?: RequestInit) => {
    const path = String(url);
    if (path.includes("?connection_id=")) return Response.json({ supervision: null });
    if (path.endsWith("/notifications")) {
      value.notification_consent = true;
      return Response.json({});
    }
    if (path.endsWith("/decision")) {
      value.offers[0].state = "accepted";
      return Response.json({ responsibility_id: id });
    }
    if (path.endsWith("/pause")) {
      value.state = "paused";
      return Response.json({});
    }
    return Response.json(value);
  });
  vi.stubGlobal("fetch", fetch);
  render(<CourseSupervision {...props} />);
  await waitFor(() =>
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: "Enable supervision" }).disabled,
    ).toBe(false),
  );
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][1]?.method).not.toBe("POST");
  fireEvent.click(screen.getByText("Enable supervision"));
  await screen.findByText("Prepare a study draft?");
  expect(
    JSON.parse(
      String(
        fetch.mock.calls.find(([url]) => String(url).endsWith("/course-supervisions"))?.[1]?.body,
      ),
    ),
  ).toEqual({
    connection_id: id,
    course_id: "101",
  });
  expect(screen.getByRole("checkbox").getAttribute("checked")).toBeNull();
  fireEvent.click(screen.getByRole("checkbox"));
  await waitFor(() => expect(screen.getByRole<HTMLInputElement>("checkbox").checked).toBe(true));
  fireEvent.click(screen.getByText("Accept and prepare draft"));
  await screen.findByText(/Draft requested/);
  const call = fetch.mock.calls.find(([url]) => String(url).endsWith("/decision"));
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ accept: true });
  fireEvent.click(screen.getByText("Pause supervision"));
  await waitFor(() =>
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: "Pause supervision" }).disabled,
    ).toBe(true),
  );
});

it("clears saved offers and disables actions when the session expires", async () => {
  sessionStorage.setItem(`wrytely:course-supervision:user_alice:${id}:101`, id);
  const expired = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => Response.json({ detail: "Expired" }, { status: 401 })),
  );
  render(<CourseSupervision {...props} onSessionExpired={expired} />);
  await waitFor(() => expect(expired).toHaveBeenCalledOnce());
  expect(screen.queryByText("Prepare a study draft?")).toBeNull();
  expect(
    screen.getByRole<HTMLButtonElement>("button", { name: "Enable supervision" }).disabled,
  ).toBe(true);
});

it("does not enable an unselected course or expose a late prior-account response", async () => {
  sessionStorage.setItem(`wrytely:course-supervision:user_alice:${id}:101`, id);
  let resolve: (value: Response) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>((done) => {
          resolve = done;
        }),
    ),
  );
  const view = render(<CourseSupervision {...props} />);
  view.rerender(<CourseSupervision {...props} userId="user_bob" selected={false} />);
  resolve(Response.json({ supervision: monitor() }));
  await waitFor(() => expect(screen.queryByText("Prepare a study draft?")).toBeNull());
  expect(
    screen.getByRole<HTMLButtonElement>("button", { name: "Enable supervision" }).disabled,
  ).toBe(true);
});

it.each([
  ["model_provider_unavailable", "The model service is unavailable."],
  ["model_request_timed_out", "The model request timed out. Its outcome is unknown."],
  [
    "model_connection_failed",
    "The connection to the model service failed. Its outcome is unknown.",
  ],
  [
    "PRIVATE provider body/token",
    "Supervision needs attention. The saved reason is not recognized.",
  ],
])(
  "explains a blocked %s without leaking raw failure text or starting a retry",
  async (reason, label) => {
    const value = {
      ...monitor(),
      state: "blocked",
      offers: [],
      reason,
    };
    const fetch = vi.fn(async (url: unknown) =>
      Response.json(String(url).includes("?connection_id=") ? { supervision: value } : value),
    );
    vi.stubGlobal("fetch", fetch);
    render(<CourseSupervision {...props} />);
    await screen.findByText((content) => content.includes(label));
    expect(screen.queryByText(/PRIVATE provider body\/token/)).toBeNull();
    expect(screen.getByText(/No automatic retry was started/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /retry|resume/i })).toBeNull();
    expect(fetch.mock.calls).toHaveLength(2);
  },
);

it("shows ready source-change reassessment without describing it as a blocked retry", async () => {
  const value = {
    ...monitor(),
    state: "ready",
    offers: [],
    reason: "source_changed_during_decision",
    next_check_at: "2026-11-05T03:44:10Z",
  };
  const fetch = vi.fn(async (url: unknown) =>
    Response.json(String(url).includes("?connection_id=") ? { supervision: value } : value),
  );
  vi.stubGlobal("fetch", fetch);
  render(<CourseSupervision {...props} />);
  await screen.findByText(/Course evidence changed while this check was running/);
  expect(screen.queryByText(/No automatic retry was started/)).toBeNull();
  expect(screen.getByText(/Reassessment is scheduled/)).toBeTruthy();
  expect(fetch.mock.calls).toHaveLength(2);
});
