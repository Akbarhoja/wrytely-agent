# M one-course assembly

Supervisor assignment: [coordination claim](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6615708768).
Plan: [one-course delivery](ONE-COURSE-DELIVERY.md). Shared boundary:
[course supervision v1](contracts/COURSE-SUPERVISION-v1.md).

## Session HTTP

All routes authenticate through the existing verified-session dependency. No
request may choose its owner. Responses use `Cache-Control: no-store`; internal
exceptions return a generic unavailable response without diagnostic contents.
Existing bounded JSON handling caps requests at 16 KiB. Query parameters and
additional body fields are rejected. No HTTP route starts inference or sends a
message. A call ceiling is not paid activation approval.

| Method | Path                                                      | Input / result                                                                                          |
| ------ | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| POST   | `/v1/course-supervisions`                                 | `connection_id`, `course_id`, optional integer `call_limit` (1–20, default 6); returns published status |
| GET    | `/v1/course-supervisions/{id}`                            | Persisted student status and offers                                                                     |
| POST   | `/v1/course-supervisions/{id}/pause`                      | Empty body; fences supervision, including after source disconnect                                       |
| POST   | `/v1/course-supervisions/{id}/offers/{offer_id}/decision` | Required boolean `accept`; returns state and nullable `responsibility_id`                               |

Enable returns the student status projection rather than the raw Store row, so
leases and inspection snapshots stay internal. Enable replay does not refill the
Store allowance. Acceptance passes only the Store's returned `draft_request` to
the existing Canvas draft method. Its stable request key recovers repeated requests
and a crash after recording acceptance. Decline creates no draft. Private artifact
reads remain on existing authenticated result routes.

## Remaining assembly

- Build the supervision web controls against these endpoints and the existing
  private result UI. A retains collector and remaining P1 implementation.
- Prepare explicit service scheduling using stored due-user identities and the
  published runtime, with health/stop/restart controls. Paid activation remains off
  until a concrete bounded candidate is approved.
- Proactive offers need A's distinct persisted delivery authorization, explicit
  proactive consent, source/control fences and actual approved offer template.
  Reply-only authorization cannot dispatch them.
- Reply-template opt-in is separately authorized for implementation under the new
  supervisor assignment. Provider approval and live sends remain separate gates.
- File/revision assembly consumes published Store/rendering boundaries as A makes
  them executable. No parallel interpreter, Store or delivery queue is introduced.

## Acceptance limits

This HTTP slice does not prove installed Canvas collection, continuous operation,
model quality, artifact revision/rendering or WhatsApp delivery. Last shared account
restriction state remains unknown; no live send or retry is included. Test evidence
must name the exact candidate and distinguish synthetic integration from live proof.
