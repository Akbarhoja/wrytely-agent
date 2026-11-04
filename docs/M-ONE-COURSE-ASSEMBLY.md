# M one-course assembly

See the [integration evidence handoff](M-INTEGRATION-EVIDENCE.md) for scoped check
results, synthetic Word examples and remaining acceptance gates.

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

- GET `/v1/course-supervisions?connection_id=...&course_id=...`: read-only owned
  status lookup, returning nullable `supervision`. Never enrolls or refills. The
  web controls use this rather than browser persistence or automatic enable calls.

- POST `/v1/course-supervisions/{id}/notifications`: strict boolean `consent` for
  separate proactive opt-in.
- POST `/v1/course-supervisions/{id}/offers/{offer_id}/delivery`: empty body;
  idempotent Store-owned enqueue, never a caller payload or direct send.
- GET `/v2/artifacts/{id}/file`: immutable checked Word bytes with attachment,
  digest and check headers; no public file link.
- POST `/v2/artifacts/{id}/revisions`: student `instructions` and stable
  `request_key` handed to the existing private revision task method.
- POST `/v2/artifacts/{id}/delivery`: empty body; explicit request for the checked
  artifact through the existing one-use outbox. No caller recipient/URL/file body.

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

Checked document dispatch uploads the authorized bytes to the configured account,
binds the returned media ID to the action/account/hash, re-reads current checked
bytes and authority, then sends a document referencing that media ID. Upload and
send each have a bounded timeout and no retry. Both private reads must match the
original descriptor. Missing or ambiguous results remain unknown. Current-window
authorization and signed receipt reconciliation remain in the original Store.
The adapter rejects mismatched bytes/filename/hash and media from another action
or account before sending. No public file URL is introduced.

Protocol references: Meta's [upload endpoint example](https://www.postman.com/meta/whatsapp-business-platform/request/q3rsuse/upload-image)
and its [document message schema](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/messages/document/).
The SDK reference is archived; native provider acceptance remains an explicit live
gate. The current Cloud API reference fetch returned HTTP429 during this audit.

## Signed WhatsApp commands

The exact raw-body signature and configured account/phone filters run before the
bounded deterministic parser. Replies to an authenticated original offer/file can
use `/accept`, `/decline`, `/file` or `/revise` followed by feedback. An optional
explicit owned UUID target is supported for controlled tests and recovery; the
student's normal flow replies to the message. Bare natural-language agreement is
not converted into acceptance. Only revision accepts feedback (at most 4000
characters). Slash-prefixed input is reserved for explicit commands; malformed or
unknown commands never fall through to generic reasoning.

The app constructs A's typed envelope from signed sender/provider time/reply context
and calls the original atomic intake. It never chooses an owner or issues SQL to
resolve a phone. Commands skip generic ingestion and its chat task. LINK and ordinary
messages keep their existing behavior. Missing/invalid timestamps or reply context
cannot grant acceptance. Current-link/account/owned-target checks, replay receipts
and action idempotency remain in the existing Store/028 boundary. Permanent rejection
is safely acknowledged with no outward send; unexpected persistence failure returns
503 without private diagnostics, allowing the provider's idempotent event replay.
Valid signed delivery-status siblings still persist after malformed commands.

## Connected signed rehearsal

[Signed journey test](../tests/test_signed_course_journey.py) reuses A's original
one-course journey unchanged and routes command/receipt entrypoints through the
actual HMAC-signed webhook. Its test-only facade delegates every other operation
to the same real Store and captures actual handler results. Six command requests
and replays plus two signed delivery callbacks cover acceptance, checked file,
revision, immutable versions and changed-source fencing. No authentication flag,
parallel runtime or fabricated Store receipt is used. Scripted models and simulated
provider transport remain explicit; this is not live Meta, phone or native Word
acceptance. The first isolated rehearsal passed in 13.76 seconds, with one existing
Starlette/httpx deprecation warning.

## Remaining acceptance

- Student web controls now wire explicit supervision/notification/offer decisions,
  private Word download/revision and explicit file enqueue through a narrow session
  proxy. A retains collector and remaining P1 implementation.
- Saved offer enqueue recovery uses the published internal selector independently
  of paid model due time, including restart/unknown-outcome exclusions.
- Validate the final signed command slice with focused, full and Linux CI evidence;
  retain permanent rejection versus unpersisted failure distinctions.
- Verify actual template approval, owner business verification and bounded live
  activation before WhatsApp/model operations.

## Acceptance limits

This HTTP slice does not prove installed Canvas collection, continuous operation,
model quality or WhatsApp delivery. Owner confirmed account restriction pending
business verification (submitted and under review); no live send or retry is included. Word/phone visual
acceptance is unverified. Test evidence
must name the exact candidate and distinguish synthetic integration from live proof.
