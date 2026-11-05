/** Only fixed command labels cross into the view; nested result bodies stay unrendered. */
export type CommandStatus = { label: string; receivedAt: string };
const kinds: Record<string, string> = {
  accept_offer: "Acceptance command recorded.",
  decline_offer: "Decline command recorded.",
  revise_artifact: "Revision request recorded.",
  send_artifact: "File request recorded.",
};
const reasons: Record<string, string> = {
  invalid_command: "The command format was not valid.",
  source_refresh_required: "Course evidence needs refreshing before this command can proceed.",
  command_unavailable: "The requested action is unavailable.",
};
const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
export function commandStatus(value: unknown): CommandStatus | null {
  if (value === undefined || value === null) return null;
  const fail = () => {
    throw Error("Invalid Telegram command status");
  };
  if (
    !object(value) ||
    typeof value.received_at !== "string" ||
    value.received_at.length > 64 ||
    !Number.isFinite(Date.parse(value.received_at)) ||
    !object(value.command_result)
  )
    return fail();
  const result = value.command_result;
  if (
    value.outcome === "command_applied" &&
    result.state === "applied" &&
    typeof result.kind === "string" &&
    Object.hasOwn(kinds, result.kind) &&
    typeof result.target_id === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(result.target_id) &&
    object(result.result)
  )
    return { label: kinds[result.kind], receivedAt: value.received_at };
  if (
    value.outcome === "command_rejected" &&
    result.state === "rejected" &&
    typeof result.reason === "string" &&
    Object.hasOwn(reasons, result.reason)
  )
    return { label: reasons[result.reason], receivedAt: value.received_at };
  return fail();
}
