import { expect, it } from "vitest";
import { supervisionReason } from "../lib/supervision-reason";
it.each([
  ["model_provider_unavailable", "unavailable"],
  ["model_rate_limited", "rate-limited"],
  ["model_access_denied", "denied access"],
  ["model_not_found", "could not be found"],
  ["model_response_incomplete", "incomplete"],
  ["model_request_failed", "request failed"],
  ["episode_failed_or_unknown", "outcome is unknown"],
  ["inference_outcome_unknown", "unknown outcome"],
  ["call_limit", "reserved-check limit"],
  ["source_changed_during_decision", "evidence changed"],
])("labels %s without displaying a raw code", (code, phrase) => {
  const label = supervisionReason(code);
  expect(label).toContain(phrase);
  expect(label).not.toContain(code);
});
it.each(["PRIVATE provider body/token", "__proto__", null, {}, 42])(
  "never echoes unknown data %s",
  (value) => {
    expect(supervisionReason(value)).toBe(
      "Supervision needs attention. The saved reason is not recognized.",
    );
  },
);
