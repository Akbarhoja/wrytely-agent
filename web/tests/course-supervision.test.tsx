import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CourseSupervision } from "../components/course-supervision";

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
