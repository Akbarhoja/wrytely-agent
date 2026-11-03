// Native extension controls. No storage, source reads or credentials in view state.
const TYPE = "wrytely.canvas.host.v1";
const states = new Set([
  "paused",
  "ready",
  "progress",
  "finished",
  "awaiting_resources",
  "cooldown",
  "blocked",
  "busy",
]);
const reasonCopy = {
  login_required: "Sign in to Canvas, then verify your identity again.",
  canvas_account_changed:
    "The Canvas account changed. Pair and verify this browser again.",
  canvas_session_unavailable:
    "Canvas could not verify this session. Check your sign-in.",
  reconnect_required: "Reconnect this browser using a new pairing code.",
  discovery_context_changed:
    "The saved scan no longer matches the current course selection or connection. Collection stopped; ask Wrytely support to check recovery before pairing again.",
  discovery_journal_invalid:
    "The saved collection checkpoint could not be validated. Collection stopped; ask Wrytely support to check recovery.",
  discovery_reconciliation_required:
    "The saved checkpoint needs reconciliation with Wrytely. Collection stopped; ask Wrytely support to check recovery.",
  host_failed:
    "The browser collector stopped unexpectedly. No automatic retry is running. Ask Wrytely support to check recovery.",
  pause_required: "Pause collection before changing the connection.",
  identity_in_progress: "Wait for identity verification to finish.",
  storage_unavailable:
    "Browser settings could not be saved. Refresh status before continuing.",
  rate_limited: "Canvas asked to wait before the next collection attempt.",
  permission_denied:
    "Canvas did not allow this read. Check the connection and course access.",
};
// Display only internal, fixed codes. Never echo a source/provider error string.
const diagnosticReasons = new Set([
  "invalid_document_input",
  "invalid_collection",
  "unsafe_pagination",
  "pagination_cycle",
  "invalid_pagination",
  "invalid_provider_id",
  "size_limit",
  "login_or_non_json",
  "invalid_response",
  "unsafe_file_url",
  "unsafe_file_redirect",
  "collector_failed",
  ...[
    "ambiguous_observation_time",
    "document_conflict",
    "document_expired",
    "document_not_ready",
    "resource_format_conflict",
    "duplicate_resource_item",
    "finish_previous_resource",
    "resource_rewind",
    "checkpoint_changed",
    "course_not_discovered",
    "course_scope_limit",
    "cursor_cycle",
    "duplicate_course_page",
    "generation_changed",
    "identity_required",
    "incomplete_resource",
    "lease_expired",
    "lease_replaced",
    "pagination_complete_or_limit",
    "reconnect_required",
    "replay_conflict",
    "resource_not_selected",
    "resource_terminal",
    "resources_open",
    "resume_existing_scan",
    "scan_terminal",
    "scope_changed",
    "subject_changed",
  ].map((code) => `discovery_${code}`),
]);
const headings = {
  paused: "Collection is paused",
  ready: "Collection is enabled",
  progress: "Collection is enabled",
  finished: "Last scan finished",
  awaiting_resources: "Some course content is unavailable",
  cooldown: "Waiting before the next attempt",
  blocked: "Collection needs attention",
  busy: "Browser is busy",
};

export function createControls({
  send,
  onChange = () => {},
  onCodeClear = () => {},
}) {
  let alive = true,
    epoch = 0,
    readSequence = 0,
    dataPending = null,
    controlPending = false;
  let view = {
    state: "unknown",
    enabled: null,
    running: false,
    verified: false,
    uncertain: true,
    heading: "Check collection status",
    coverage: "Coverage not measured in this view.",
    feedback: "",
    tone: "info",
    fieldError: "",
  };
  const snapshot = () => ({
    ...view,
    busy: dataPending,
    controlBusy: controlPending,
  });
  const emit = () => {
    if (alive) onChange(snapshot());
  };
  function unknown(text) {
    view = {
      ...view,
      state: "unknown",
      enabled: null,
      verified: false,
      uncertain: true,
      heading: "Status is unknown",
      feedback: text,
      tone: "warning",
    };
  }
  function accept(reply) {
    if (
      !reply ||
      typeof reply !== "object" ||
      !states.has(reply.state) ||
      typeof reply.enabled !== "boolean" ||
      (reply.state === "paused" && reply.enabled) ||
      ([
        "ready",
        "progress",
        "finished",
        "awaiting_resources",
        "cooldown",
      ].includes(reply.state) &&
        !reply.enabled)
    ) {
      unknown("Refresh status before continuing. No action was retried.");
      return false;
    }
    view = {
      ...view,
      state: reply.state,
      enabled: reply.enabled,
      running: reply.running === true,
      uncertain: false,
      heading: headings[reply.state],
      coverage:
        reply.coverage === "partial"
          ? "The last reported step has partial coverage."
          : reply.coverage === "complete"
            ? "The last reported scan has complete coverage; other content may still be unavailable."
            : "Coverage not measured in this view.",
    };
    if (reply.state === "blocked") {
      view.verified = false;
      view.feedback =
        reasonCopy[reply.reason] ??
        (diagnosticReasons.has(reply.reason)
          ? `Collection stopped. Diagnostic code: ${reply.reason}. Keep it paused and share this code with Wrytely support.`
          : "Collection needs attention. Refresh status and verify the connection.");
      view.tone = "warning";
    }
    return reply.state !== "blocked";
  }
  async function refresh() {
    if (!alive) return false;
    const stamp = epoch,
      sequence = ++readSequence;
    try {
      const reply = await send({ type: TYPE, action: "status" });
      if (alive && stamp === epoch && sequence === readSequence) {
        if (accept(reply)) {
          view.feedback = "Browser status refreshed.";
          view.tone = "info";
        }
        emit();
      }
    } catch {
      if (alive && stamp === epoch && sequence === readSequence) {
        unknown("Could not read browser status. Refresh to try again.");
        emit();
      }
    }
    return true;
  }
  async function perform(action, { code, consent = false } = {}) {
    if (
      !alive ||
      !["pair", "bind", "enable", "disable", "collect"].includes(action)
    )
      return false;
    if (
      controlPending ||
      (dataPending && !(action === "disable" && dataPending === "collect"))
    )
      return false;
    view.fieldError = "";
    if (
      action === "pair" &&
      (typeof code !== "string" || !/^[A-Za-z0-9_-]{32}$/.test(code))
    ) {
      view.fieldError =
        "Enter the 32-character pairing code from your Wrytely account.";
      emit();
      return false;
    }
    if (
      ["pair", "bind"].includes(action) &&
      (view.enabled !== false || view.uncertain)
    ) {
      view.feedback = "Refresh status and pause collection before connecting.";
      emit();
      return false;
    }
    if (
      action === "enable" &&
      (!view.verified || !consent || view.enabled !== false || view.uncertain)
    ) {
      view.feedback =
        "Verify your Canvas identity and confirm background reads first.";
      emit();
      return false;
    }
    if (action === "collect" && (view.enabled !== true || view.uncertain))
      return false;
    const control = ["enable", "disable"].includes(action);
    const stamp = ++epoch;
    if (control) controlPending = true;
    else dataPending = action;
    view.feedback =
      action === "disable"
        ? "Saving pause. The current step may still finish."
        : "Waiting for the browser…";
    view.tone = "info";
    if (action === "pair") onCodeClear();
    emit();
    try {
      const reply = await send({
        type: TYPE,
        action,
        ...(action === "pair" ? { code } : {}),
      });
      if (!alive || stamp !== epoch) return false;
      if (
        action === "disable" &&
        (reply?.durable !== true ||
          reply?.enabled !== false ||
          reply?.state !== "paused")
      ) {
        unknown(
          "Pause was not saved. Refresh status before closing this window.",
        );
        return false;
      }
      const success =
        action === "pair"
          ? reply?.state === "pending_identity" && reply.enabled === false
          : action === "bind"
            ? ["connected", "active"].includes(reply?.state) &&
              reply.enabled === false
            : action === "enable"
              ? reply?.state === "ready" && reply.enabled === true
              : action === "disable"
                ? true
                : [
                    "progress",
                    "finished",
                    "awaiting_resources",
                    "cooldown",
                  ].includes(reply?.state) && reply.enabled === true;
      if (!success) {
        if (reply?.state === "busy" && typeof reply.enabled === "boolean") {
          accept(reply);
          view.verified = false;
          view.feedback =
            "Another browser operation is running. Refresh status before continuing.";
          view.tone = "warning";
        } else if (reply?.state === "blocked" && reply.enabled === false)
          accept(reply);
        else
          unknown(
            "The browser did not confirm the action. Refresh status before continuing; it was not retried.",
          );
        return false;
      }
      if (action === "pair" && reply?.state === "pending_identity") {
        view = {
          ...view,
          state: "paused",
          enabled: false,
          uncertain: false,
          verified: false,
          heading: headings.paused,
          feedback: "Browser paired. Verify your Canvas identity next.",
          tone: "success",
        };
        return true;
      }
      if (action === "bind" && ["connected", "active"].includes(reply?.state)) {
        view = {
          ...view,
          state: "paused",
          enabled: false,
          uncertain: false,
          verified: true,
          heading: headings.paused,
          feedback: "Canvas identity verified for this view.",
          tone: "success",
        };
        return true;
      }
      const accepted = accept(reply);
      if (accepted) {
        view.feedback =
          action === "disable"
            ? "Pause saved. No new steps will start; the current step may finish."
            : action === "enable"
              ? "Collection enabled. Browser availability and your Canvas session still apply."
              : "Collection status updated. Refresh to check current activity.";
        view.tone = "success";
      }
      return accepted;
    } catch {
      if (alive && stamp === epoch)
        unknown(
          "The action outcome is unknown. Refresh status before continuing; it was not retried.",
        );
      return false;
    } finally {
      if (control) controlPending = false;
      else dataPending = null;
      emit();
    }
  }
  function dispose() {
    alive = false;
    epoch++;
    onCodeClear();
  }
  emit();
  return Object.freeze({ snapshot, refresh, perform, dispose });
}

export function mountControls({ document, send, openOptions = () => {} }) {
  const byId = (id) => document.getElementById(id);
  let controls;
  function render(view) {
    byId("heading").textContent = view.heading;
    byId("coverage").textContent = view.coverage;
    byId("feedback").textContent = view.feedback;
    byId("feedback").dataset.tone = view.tone;
    byId("activity").textContent =
      view.running || view.busy === "collect"
        ? "A running step may finish after you pause."
        : "Collection depends on this browser and your signed-in Canvas session.";
    byId("identity-status").textContent = view.verified
      ? "Identity checked in this view."
      : "Identity has not been checked in this view.";
    byId("code-error").textContent = view.fieldError;
    byId("code").setAttribute("aria-invalid", String(Boolean(view.fieldError)));
    const locked = Boolean(view.busy || view.controlBusy);
    byId("pair").disabled = locked || view.enabled !== false || view.uncertain;
    byId("bind").disabled = locked || view.enabled !== false || view.uncertain;
    byId("enable").disabled =
      locked ||
      !view.verified ||
      view.enabled !== false ||
      view.uncertain ||
      !byId("consent").checked;
    byId("collect").disabled =
      locked || view.enabled !== true || view.uncertain;
    byId("disable").disabled =
      view.controlBusy ||
      (view.busy && view.busy !== "collect") ||
      view.enabled === false;
    byId("controls").setAttribute("aria-busy", String(locked));
    byId("pair").textContent =
      view.busy === "pair" ? "Pairing…" : "Pair browser";
    byId("bind").textContent =
      view.busy === "bind" ? "Verifying…" : "Verify Canvas identity";
  }
  controls = createControls({
    send,
    onChange: render,
    onCodeClear: () => {
      byId("code").value = "";
      byId("code").type = "password";
      byId("reveal").textContent = "Show code";
      byId("reveal").setAttribute("aria-pressed", "false");
    },
  });
  byId("pair-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await controls.perform("pair", { code: byId("code").value });
    if (controls.snapshot().fieldError) byId("code").focus();
  });
  for (const action of ["bind", "enable", "disable", "collect"])
    byId(action).addEventListener("click", () => {
      void controls.perform(action, { consent: byId("consent").checked });
    });
  byId("refresh").addEventListener("click", () => {
    void controls.refresh();
  });
  byId("consent").addEventListener("change", () => render(controls.snapshot()));
  byId("reveal").addEventListener("click", () => {
    const shown = byId("code").type === "password";
    byId("code").type = shown ? "text" : "password";
    byId("reveal").textContent = shown ? "Hide code" : "Show code";
    byId("reveal").setAttribute("aria-pressed", String(shown));
  });
  byId("options").addEventListener("click", () => {
    try {
      Promise.resolve(openOptions()).catch(() => {});
    } catch {
      /* No private logging. */
    }
  });
  for (const id of ["options", "reveal", "refresh"]) byId(id).disabled = false;
  void controls.refresh();
  return controls;
}
