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

Additional session routes:

- POST `/v1/course-supervisions/{id}/notifications`: strict boolean `consent` for
  separate proactive opt-in.
- POST `/v1/course-supervisions/{id}/offers/{offer_id}/delivery`: empty body;
  idempotent Store-owned enqueue, never a caller payload or direct send.
- GET `/v2/artifacts/{id}/file`: immutable checked Word bytes with attachment,
  digest and check headers; no public file link.
- POST `/v2/artifacts/{id}/revisions`: student `instructions` and stable
  `request_key` handed to the existing private revision task method.

Enable returns the student status projection rather than the raw Store row, so
leases and inspection snapshots stay internal. Enable replay does not refill the
Store allowance. Acceptance passes only the Store's returned `draft_request` to
the existing Canvas draft method. Its stable request key recovers repeated requests
and a crash after recording acceptance. Decline creates no draft. Private artifact
reads remain on existing authenticated result routes.

## Transport and service assembly

The existing WhatsApp worker opts into typed payload support. It passes trusted
reply and offer configuration separately to Store authorization and dispatches only
the returned text/template payload once. Accepted/unknown outcomes and the existing
signed receipt path are preserved. Empty template configuration still holds sends
outside the conversation window. Code does not verify real provider approval.

The explicit course service uses `BudgetedMetaRouter` and trusted persisted due
identities. See [service preparation](../deploy/ONE-COURSE-SERVICES.md) for entrypoints,
health, stop and restart limits. No startup migration, budget grant or direct send.

## Remaining assembly and acceptance

- Build the supervision web controls against these endpoints and the existing
  private result UI. A retains collector and remaining P1 implementation.
- Recover a saved offer awaiting enqueue independently of the next paid model check,
  using A's requested internal selector. No parallel queue is introduced.
- Complete signed linked-inbound acceptance/revision commands and separately
  authorized phone file delivery once the channel boundary is ready.
- Verify actual template approval, owner business verification and bounded live
  activation before WhatsApp/model operations.

## Acceptance limits

This HTTP slice does not prove installed Canvas collection, continuous operation,
model quality or WhatsApp delivery. Owner confirmed account restriction pending
business verification; no live send or retry is included. Word/phone visual
acceptance is unverified. Test evidence
must name the exact candidate and distinguish synthetic integration from live proof.
