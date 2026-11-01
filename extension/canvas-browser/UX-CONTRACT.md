# Private browser control behavior

Scope: popup.html and options.html share ui.mjs. Existing host/client/journal own
all connection identity, preferences, authorization and collection. UI stores no
code, source, credentials or account identifiers. Locale is English.

| Capability | Canonical owner                  | Source of truth | Allowed variants       | Verification                  |
| ---------- | -------------------------------- | --------------- | ---------------------- | ----------------------------- |
| Form       | ui.mjs/native fields             | This contract   | Pair code/consent      | ui.test.mjs + preview         |
| Scrollbar  | styles.css global baseline       | Root DESIGN.md  | Popup/options geometry | Static audit + narrow preview |
| Toast      | Inline feedback/status in ui.mjs | This contract   | Info/warning/success   | ui.test.mjs + preview         |

- Opening reads local host status only. No enable, bind, redeem, source request or
  permission grant occurs automatically. Unknown status never appears connected.
- Pair code is masked with an accessible reveal control; no persistence, URL,
  logging or automatic retry. Clear after dispatch and page exit. Invalid input
  has an associated correction message and receives focus.
- Verify Canvas identity is explicit. Enable requires confirmation of the stated
  background-read consequence and a successful identity check in this view.
  Existing enabled collection can always be paused without repeating identity.
- Pause stops new steps, not remaining requests in an already-running bounded
  step. Pause remains reachable while a collect command awaits completion.
  Durable:false never appears as a saved pause. Alarms are opportunities, not an
  uptime or exact-timing promise. No source completeness is inferred from enabled.
- Duplicate data commands are blocked. A newer control action fences older UI
  replies. On uncertain command outcome show unknown and permit status refresh;
  never retry a mutation automatically. Refresh itself reads preferences only.
- Feedback is stable, inline, semantic and persistent. Native buttons/labels and
  keyboard behavior, visible focus, polite live status, semantic busy/disabled
  states and natural scrolling apply to both pages. No browser dialogs.
- Package origins are fixed at local build time. No text field changes the API
  target, ownership or host permissions. Settings link uses openOptionsPage only
  on a user gesture. There is no disconnect, OAuth, send or install action.

Real installed Chrome behavior remains separately unverified until an authorized
browser lifecycle acceptance run. Synthetic preview is not proof of source access.
