/** Fixed operator-reviewed labels. Never render arbitrary provider text as a reason. */
const labels: Record<string, string> = {
  model_provider_unavailable: "The model service is unavailable.",
  model_rate_limited: "The model service rate-limited this check.",
  model_access_denied: "The model service denied access to this check.",
  model_not_found: "The configured model could not be found.",
  model_response_incomplete: "The model response was incomplete.",
  model_request_failed: "The model request failed.",
  model_request_timed_out: "The model request timed out. Its outcome is unknown.",
  model_connection_failed: "The connection to the model service failed. Its outcome is unknown.",
  episode_failed_or_unknown: "This check failed or its outcome is unknown.",
  inference_outcome_unknown: "The previous model call has an unknown outcome.",
  call_limit: "This supervision has reached its reserved-check limit.",
  source_changed_during_decision: "Course evidence changed while this check was running.",
};
export function supervisionReason(reason: unknown): string {
  return typeof reason === "string" && Object.hasOwn(labels, reason)
    ? labels[reason]
    : "Supervision needs attention. The saved reason is not recognized.";
}
