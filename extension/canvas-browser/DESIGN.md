# Canvas browser controls

Product surface for students; English, light theme. Inherits the complete root
[design context](../../DESIGN.md), without changing web identity or shared tokens.
The popup's one job is to make Canvas collection and student control legible.

## Visual direction

Use the incumbent semester-planner palette: green primary, pale green background,
white surface, dark green text, muted secondary text and red errors. Values come
only from `web/app/globals.css :root`, extracted into packaged tokens.css at build
time. No duplicate palette is maintained here. Self-hosted Plus Jakarta Sans is
used for headings, body and controls, with weight/size as the hierarchy. Fonts are
packaged with their OFL license; no font/network request leaves the package.

One quiet status rail separates current collection state from the setup form.
No decorative counters, completion percentage or fabricated connection health.
Use the established 8px controls, 12px panel, no shadow. Popup is compact (360px)
with natural scrolling; options uses the same controls in a wider single column.
At narrow widths content wraps and actions remain reachable.

## Canonical map

| Capability          | Owner                          | Behavior                                            |
| ------------------- | ------------------------------ | --------------------------------------------------- |
| Form                | ui.mjs + native HTML fields    | Explicit actions, masked code, inline errors        |
| Feedback/Toast      | Shared status/feedback regions | Persistent text + polite live region; no dialogs    |
| Scrollbar           | styles.css global baseline     | Visible scrollbars, stable gutter, forced colors    |
| Collection controls | Existing host.mjs              | Server/client authority; no UI permission inference |

No table, select, date picker or destructive disconnect is introduced. Existing
web React primitives cannot execute in this native MV3 page; one native UI module
is shared by both extension documents. Tokens are generated from the same owner.

## States and verification

Loading/paused/collecting/cooldown/partial/blocked/unknown are text states. An open
page never probes Canvas automatically. Current-worker counts are not displayed
as durable source health. Pairing, identity verification and enable are explicit.
Colors alone never convey success. Keyboard focus, inline validation, busy state,
late-response fencing and pause-during-collection are acceptance requirements.
