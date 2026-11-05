import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TelegramConnection } from "../components/telegram-connection";
import { forward } from "../lib/forward";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const unlinked = {
  linked: false,
  preferences: null,
  latest_delivery: null,
  bot_username: "wrytely_agent_bot",
};
it("loads read-only, creates an explicit private challenge and clears it on account change", async () => {
  const fetch = vi.fn(async (url: unknown) =>
    Response.json(
      String(url).endsWith("/link")
        ? {
            message: "/start " + "a".repeat(43),
            expires_at: new Date(Date.now() + 600000).toISOString(),
            bot_username: "wrytely_agent_bot",
          }
        : unlinked,
    ),
  );
  vi.stubGlobal("fetch", fetch);
  const view = render(<TelegramConnection userId="alice" enabled />);
  await waitFor(() => expect(fetch).toHaveBeenCalledOnce());
  expect(fetch.mock.calls[0][0]).toBe("/api/agent/telegram");
  fireEvent.click(screen.getByText("Create private link message"));
  await screen.findByDisplayValue("/start " + "a".repeat(43));
  expect(
    screen.getByRole("link", { name: "Open configured Telegram bot" }).getAttribute("href"),
  ).toBe("https://t.me/wrytely_agent_bot?start=" + "a".repeat(43));
  view.rerender(<TelegramConnection userId="bob" enabled={false} />);
  expect(screen.queryByDisplayValue("/start " + "a".repeat(43))).toBeNull();
  expect(screen.getByText(/does not support \/accept/)).toBeTruthy();
});
it("requires separate false-default consents and saves only explicit preferences", async () => {
  const state = {
    ...unlinked,
    linked: true,
    preferences: {
      consent: false,
      notification_consent: false,
      timezone: "UTC",
      quiet_start: 22,
      quiet_end: 8,
    },
  };
  const fetch = vi.fn(async () => Response.json(state));
  vi.stubGlobal("fetch", fetch);
  render(<TelegramConnection userId="alice" enabled />);
  const replies = await screen.findByLabelText("Allow Telegram replies");
  expect((replies as HTMLInputElement).checked).toBe(false);
  expect(
    (screen.getByLabelText("Allow preparation notifications") as HTMLInputElement).checked,
  ).toBe(false);
  fireEvent.click(replies);
  fireEvent.click(screen.getByText("Save Telegram permissions"));
  await waitFor(() => expect(fetch.mock.calls.length).toBe(3));
  const call = fetch.mock.calls[1] as unknown as [string, RequestInit];
  expect(call[0]).toBe("/api/agent/telegram/preferences");
  expect(JSON.parse(String(call[1].body))).toMatchObject({
    consent: true,
    notification_consent: false,
  });
});
it("clears connection state and expires on a non-JSON401", async () => {
  const expired = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("upstream", { status: 401 })),
  );
  render(<TelegramConnection userId="alice" enabled onSessionExpired={expired} />);
  await waitFor(() => expect(expired).toHaveBeenCalledOnce());
  expect((screen.getByText("Create private link message") as HTMLButtonElement).disabled).toBe(
    true,
  );
});
it("proxies only the private Telegram surface, never the public webhook or forged query", async () => {
  const deps = {
    configured: true,
    backend: "http://agent.internal/",
    session: async () => ({ userId: "alice", getToken: async () => "session" }),
    fetch: vi.fn(async () => Response.json(unlinked)),
  };
  expect(
    (await forward(new Request("https://local/api/agent/telegram"), ["telegram"], deps)).status,
  ).toBe(200);
  expect(
    (await forward(new Request("https://local/api/agent/telegram?user_id=bob"), ["telegram"], deps))
      .status,
  ).toBe(400);
  expect(
    (
      await forward(
        new Request("https://local/api/agent/webhooks/telegram", { method: "POST" }),
        ["webhooks", "telegram"],
        deps,
      )
    ).status,
  ).toBe(404);
});
