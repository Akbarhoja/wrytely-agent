import { expect, it } from "vitest";
import { commandStatus } from "../lib/telegram-command-status";
const id = "00000000-0000-4000-8000-000000000001";
const at = "2026-11-05T03:44:10Z";
const applied = (kind: string) => ({
  outcome: "command_applied",
  received_at: at,
  command_result: {
    state: "applied",
    kind,
    target_id: id,
    result: { state: "ready", PRIVATE: "DO NOT RENDER" },
  },
});
it.each(["accept_offer", "decline_offer", "revise_artifact", "send_artifact"])(
  "projects a fixed %s label",
  (kind) => {
    const value = commandStatus(applied(kind));
    expect(value?.receivedAt).toBe(at);
    expect(JSON.stringify(value)).not.toContain("PRIVATE");
    expect(JSON.stringify(value)).not.toContain("DO NOT RENDER");
    expect(JSON.stringify(value)).not.toContain(id);
  },
);
it.each(["invalid_command", "source_refresh_required", "command_unavailable"])(
  "projects fixed rejection %s",
  (reason) => {
    expect(
      commandStatus({
        outcome: "command_rejected",
        received_at: at,
        command_result: { state: "rejected", reason },
      })?.label,
    ).toBeTruthy();
  },
);
it("supports missing and null older-backend data", () => {
  expect(commandStatus(undefined)).toBeNull();
  expect(commandStatus(null)).toBeNull();
});
it.each([
  {},
  { ...applied("accept_offer"), received_at: "invalid" },
  { ...applied("accept_offer"), outcome: "command_rejected" },
  applied("PRIVATE arbitrary command"),
  {
    outcome: "command_rejected",
    received_at: at,
    command_result: { state: "rejected", reason: "PRIVATE upstream body" },
  },
  {
    ...applied("accept_offer"),
    command_result: { state: "applied", kind: "accept_offer", target_id: "wrong", result: {} },
  },
])("rejects malformed receipt without echoing it", (value) => {
  expect(() => commandStatus(value)).toThrow("Invalid Telegram command status");
});
