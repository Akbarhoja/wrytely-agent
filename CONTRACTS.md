# Contracts v0.1 — foundation

Status: implemented and locally tested; live provider validation remains pending.
Boundary types: `contracts/models.py`. Database: `contracts/001_foundation.sql`.
All private operations use the verified Clerk `sub` as `user_id`.

## HTTP

Base URL: deployment configuration, not hardcoded. Bearer authentication only.
Browser obtains a short-lived session token from existing Clerk authentication and
sends `Authorization: Bearer <token>`. `__session` cookies and user-ID headers are
not accepted by this backend. CORS origins and JWT authorized parties must be
configured for the actual frontend. No credentials go into browser storage code
or source control.

| Method/path | Input | Output / semantics |
|---|---|---|
| GET /healthz | none | Process liveness only |
| GET /readyz | none | Configuration flags; never a claim that live services were tested |
| POST /v1/bootstrap | authenticated, no body | Existing or newly provisioned agent for this user |
| GET /v1/me | authenticated | Agent ID, own user ID, paused flag; 404 before bootstrap |
| POST /v1/messages | `{content}` and `Idempotency-Key` | 202 `{task_id,status}`; durable queueing, not a completed answer |
| GET /v1/messages | authenticated | Own recent messages in chronological order, at most 100 |
| GET /v1/tasks/{id} | authenticated | Own task state; 404 also for another user's task |
| GET /v1/tasks | authenticated | `{tasks}`: own latest 50 tasks, newest first; includes status, attempts, controlled error, creation time and a title clipped to 180 characters from the source message |
| POST /v1/agent/control | `{paused: true/false}` | Own agent state |

Repeat a message request with the same key and identical content to safely retrieve
the original task. Reusing its key for different content returns 409. Missing key
or invalid body returns 422. Pending-work limit returns 429. Unauthenticated or
invalid sessions return 401. Unconfigured storage returns 503.

## Background execution

`TaskLease` identifies task, agent, user and owning attempt. Only a live lease can
write events or complete. `ModelClient.turn(history, tools)` returns typed model
output and usage. Meta's Responses API is the production adapter. Test models are
only injected in tests; no runtime fake-model mode exists.

The current tool is `get_academic_context` with exactly `{}` arguments. Scope is
server-controlled. Initial context is the current message, not a synchronized
semester model. Full planner, handoff resumption and course ingestion are later
work, not hidden assumptions in the foundation contract.

## Messaging adapter boundary for B1b

`ChannelAdapter.send(recipient, text, action_id)` returns `DeliveryResult` with a
durable internal ID and accurate provider evidence. The current API does not yet
call an adapter. Discuss durable delivery tables, verified account linking,
webhook signatures and ambiguous outcomes with the lead before implementing B1b.
No phone/chat identifier is trusted as a Clerk identity without verified linking.

## Contract changes

Propose a small PR with new types, documented behavior and tests. No duplicate
database client or parallel auth mechanism. Do not alter migration 001 after it
has been deployed; add a versioned migration instead. Both engineers may inspect
all implementation code to diagnose problems.

## B1b adapter preparation — October 28

`integrations/whatsapp.py` implements raw-body HMAC signature verification, configured
business/phone filtering and text extraction, plus a single-attempt Cloud API text
sender. HTTP clients must have transport retries disabled. Provider acceptance is
not recipient delivery; timeouts, server failures and malformed successes remain
`unknown`. The action ID refers to our ledger, not provider deduplication.

These functions are not exposed as HTTP routes or called by the worker yet.
Before enabling them: persist webhook IDs uniquely, verify account/number linking,
add durable outbound intents and permission checks, enforce the conversation
window, implement approved templates and consume status callbacks. Never route a
phone number directly to a Clerk user ID. Media intake remains future work.

## B1b durable inbound path

Migration 002 adds link challenges, verified numbers, inbound IDs and a reply
outbox. Migration runner now applies ordered versioned migrations with checksum
validation; 001 is unchanged.

- `POST /v1/whatsapp/link`: Clerk-authenticated; bootstrapped accounts receive one
  single-use challenge, valid ten minutes. Reissue invalidates its predecessor.
- `POST /v1/whatsapp/unlink`: Clerk-authenticated; unlink own number, revoke pending
  challenge and cancel own queued/deferred outbound messages.
- `GET /webhooks/whatsapp`: configured token challenge verification.
- `POST /webhooks/whatsapp`: bounded raw body, app-secret signature, configured
  business and phone filtering. Persist accepted text and task atomically; unique
  provider ID prevents duplicate tasks. Unknown senders are ignored. Return 503
  when work cannot be durably accepted because of queue capacity or storage.

Worker completion for an inbound WhatsApp task atomically creates its queued reply
if the original link is still current. Web tasks do not create WhatsApp replies.
Delivery worker, status callback ingestion, template/window rules and web linking
controls are still pending. No automatic WhatsApp sends are enabled.

## A1 episode resumption

`Store.episode_history(lease)` verifies the current live lease and returns only
that task's committed model turns and tool outputs across attempts. The runtime
reconstructs the model history in event order, retains encrypted reasoning blocks,
executes pending read-only calls, and reuses a saved final response. A model turn
now records `text` as well as its full output and usage. Legacy turns without text
cannot recover their final text through this new field and may require inference.

Each episode remains bounded and total attempts remain capped. Source mutations,
new responsibilities and true next-task selection are separate future stages.
Do not add a side-effect tool to replay without an action ledger and documented
reconciliation behavior. A crash after an external action but before its checkpoint
can otherwise duplicate that action. Current tools are read-only.

## A2 responsibility planner — internal integration contract

Migration 003 adds responsibilities and typed plan/academic tasks. Trusted callers
use `Store.create_responsibility(verified_user_id, objective, request_key,
max_steps=6, pending_limit=20)` only after explicit delegation. The caller must
supply a verified session identity; do not accept user IDs generated by a model or
read from an arbitrary request body. No new HTTP endpoint or web UI is added here.
`Store.responsibilities(user_id)` returns the account's latest 50 duties.

Creation is idempotent for the same objective/key/budget and atomically queues one
planning task. Changed payload under the same key conflicts. Missing agent fails;
existing pending-work capacity is respected. Steps are internal analysis only,
not externally authorized actions or verified assignment artifacts.

The worker requests one typed `record_plan` decision from the configured model.
Choices are work, blocked or done. A saved decision survives a new worker attempt.
Applying it atomically completes the planner task and creates at most one academic
step. Finishing that step saves its result and queues the next planner atomically.
The planner sees the objective and up to 12 step records (result excerpts limited
to 4,000 characters). Model calls and attempts retain existing bounds.

A repeated step key, empty work instruction or exhausted step budget blocks the
duty. Step budget defaults to six, hard maximum twelve. Different names for
semantically repetitive work are not deterministically detected; the model is
instructed to avoid them and the hard budget bounds this failure. Failed tasks
block their responsibility after attempt exhaustion. Blocked work occupies no
worker slot. Pause prevents new claims; active tool/result writes recheck pause.

Internal task prompts use role `internal`, and internal results are excluded from
the ordinary conversation list. They must not be presented as student messages.
`done` here means internal analysis completed according to the planner; it is not
independent verification, grading, delivery, or submission. Initial done without
any work is blocked. Source/version change handling, commitment extraction,
verified artifacts, student decision requests and blocked-duty resumption are
future stages. This loop does not yet activate through ordinary chat messages.

## A2 academic memory — draft internal contract (issue #6)

Connector handoff is proposed in coordination issue #4, not yet agreed or wired.
No new HTTP endpoints, adapters or frontend controls are part of this change.
Trusted assembly must derive user identity from the verified session/connection;
a source body or model may never provide the authority to access another account.

`SourceObservation` contains source_key (stable connector/item key), external_revision,
title, reference, coverage (`snapshot`, `api`, `feed`, `group`), content and a
mandatory timezone-aware retrieved_at. Text is limited to 24,000 characters.
References are stored as evidence only; the memory layer does not fetch URLs.
Adapters must not pass credentials in content or references.

`Store.observe_source(user_id, observation)` stores immutable version evidence and
returns its ID and source_id. Repeated key/revision with identical evidence returns
the original version and original retrieval time; it does not manufacture a fresh
sync. Changed evidence under the same revision raises RequestConflict. Distinct
versions with equal retrieval time conflict. A late observation is preserved but
cannot displace a version with a newer retrieval timestamp. This orders recorded
observations, not arbitrary vendor revision strings. Adapters must reconcile vendor
ordering where necessary. Retrieval timestamps over five minutes in the future
are rejected. Unprovisioned identities fail.

`Store.bind_source(user_id, responsibility_id, source_id)` explicitly attaches one
owned source to one owned duty, idempotently; max eight sources per responsibility.
Before the initial plan starts, binding enriches its memory revision atomically.
Once work starts, adding a source blocks old work as source_changed. No cross-user
or unbound source is exposed to the planner.

`Store.record_source_fact(lease, version_id, claim, quote)` is a fenced internal
storage boundary, not a model tool or a public route in this stage. It requires a
current source version bound to this responsibility and an exact substring quote.
Identical fact retries deduplicate by a SHA-256 digest of claim/quote. Claim and
quote limits are 2,000 characters each. Exact quote validation establishes text
presence only, not that the quote supports the claim. A3 must implement that check.

The planner/context now receives academic_memory: up to eight source excerpts
(6,000 characters each, with truncation flags), version IDs/revisions, references,
coverage and retrieval timestamps; up to 50 recent facts with current-version flags.
A fixed 24-hour heuristic flags freshness review; it is not a provider freshness SLA
or proof that a portal was checked. Snapshot input does not monitor later changes.

Promoting a newly observed version increments attached duties' memory revision,
blocks queued/running tasks, revokes their leases and blocks each affected duty
with source_changed. Past facts/results remain for audit; old facts are flagged
noncurrent and old step results stale. Task commits also check the responsibility
revision. A stale saved model/planning turn cannot complete or spawn fresh work.
This stage stops stale work; automatic revision/resumption belongs to A4. Existing
step budgets are not reset. Source evidence cannot expand action permissions.

## Delivery storage, issue #8 — draft typed handoff to #5

Stacked on memory PR #7; migration 005 preserves 001–004. Contract definitions:
`contracts/delivery.py`. Store implementation: `shared/delivery_store.py` composed
into existing Store. No network IO, transport, callback parsing or worker assembly
is implemented here. Murtazo must review/agree this typed handoff before wiring it.

- `claim_whatsapp_delivery(worker_id, lease_seconds=60)` returns DeliveryClaim or
  None. Worker ID <=100 chars, lease 5–300 seconds. Claim contains action/agent/task
  IDs, recipient, content, persisted link_generation, worker_id, attempt_token and
  deadline. It atomically changes queued/due deferred to sending. Expired sending
  becomes unknown, including attempts that may not have dispatched: conservative
  recovery avoids blind resend. Unknown/accepted/failed/cancelled are not reclaimed.
- `authorize_whatsapp_send(claim, business_id=..., phone_number_id=...)` returns
  SendAuthorization: permitted with authoritative recipient/text, held with reason
  and retry_at, or cancelled with reason. It locks agent then action, validates
  attempt ownership/expiry, current link generation and phone, pause, completed
  reply task, explicit consent, timezone/quiet-hour preferences, trusted inbound
  event timestamp and text length <=4096. Internal academic/plan results are never
  deliverable through this reply path. Source-dependent artifact delivery must use
  a later verified-artifact contract; it is not implicitly authorized here.
- Permitted authorization atomically stamps dispatch_at and business/number IDs.
  Repeating authorization raises LeaseLost. Worker must send immediately using the
  returned payload ONCE. Do not reuse authorization after restarting. There is a
  residual database-authorization/network-dispatch race: pause/unlink after this
  boundary cannot recall an in-flight request. Never claim stronger cancellation.
- `record_whatsapp_result(claim, DeliveryResult)` requires the live owning attempt,
  prior dispatch authorization and matching internal_id. Only accepted (with
  provider_ref), failed or unknown are valid transport evidence. It reconciles
  stored early callbacks if a reference is known. Late/stale result writes raise
  LeaseLost, storage failures are not success, and no result path schedules resend.
- `record_whatsapp_status(event, business_id=..., phone_number_id=...)` accepts
  WhatsAppStatusEvent ONLY after signature validation by Murtazo's assembly.
  Match configured account/number, provider reference AND recipient; never infer
  account ownership from recipient alone. Record event evidence idempotently.
  delivered/read aggregate to delivered; failed overrides sent/accepted; sent
  cannot override failed; delivered never regresses. Read evidence remains in the
  event record, not a fabricated aggregate read state.
- Callback-before-response is persisted unmatched and reconciled when the exact
  provider reference is saved. Callback and result writes serialize by reference.
  Orphans are retained seven days, capped at 10,000 with an explicit failure when
  full. Expired orphan cleanup occurs on callback ingestion. Without a known
  provider reference (lost send response), an orphan stays unmatched; manual/provider
  reconciliation is required and no automatic resend is permitted.

Trusted assembly calls `record_whatsapp_inbound_time(provider_id, sender, event_at)`
after signature validation AND successful durable inbound ingestion. It requires
a persisted inbound ID matching the current phone/link, timezone-aware provider
event time and at most five minutes future skew; stored time is capped to receipt
and never moves backwards. Old signed events do not reopen an expired 24-hour
window. Receipt-only `last_inbound_at` is not used for send eligibility. Existing
links retain unknown event time. New link generations are random; historical reply
rows without a proven generation are cancelled at authorization, never backfilled
with assumed permission.

`set_communication_preferences(verified_user_id, consent=bool, timezone=IANA,
quiet_start=0..23, quiet_end=0..23)` persists explicit account-scoped preferences.
Equal start/end explicitly disables quiet hours; overnight ranges are supported.
No preference rows are inferred for existing students. Missing preferences,
revoked consent, pause, unknown inbound time, quiet hours and oversized text hold
sending for a five-minute reevaluation; ownership/result mismatch cancels. No
model/source can set preferences by calling an untrusted interface.

IMPORTANT REMAINING GAP: an expired conversation window returns held with
`approved_template_required`. This PR intentionally does not invent an approved
template name, parameters or permission. Approved-template configuration/payload
support needs the next jointly agreed contract before proactive >24-hour sends
can work. Murtazo's transport may prepare templates independently, but must not
bypass this hold. Setup/API preference endpoints, timestamp parser wiring, delivery
worker and signed callback assembly remain Murtazo's tasks. No live send enabled.

## Private WhatsApp connection read — issue #18, requested by #17

`Store.whatsapp_connection(verified_user_id)` returns None before provisioning;
otherwise `{linked: bool, phone_last4: str|null, preferences: object|null,
latest_delivery: object|null}`. Preferences, when saved, contain consent (bool),
timezone (IANA string), quiet_start and quiet_end (integers). Explicit false/zero
values are preserved. Missing preferences remain null. Latest delivery, when any,
contains state (existing persisted enum), reason (nullable controlled hold reason)
and retry_at (nullable aware datetime, serialized as ISO by API assembly).

State `sending` means a pending attempt, not confirmed delivery. accepted means
provider acceptance; only delivered reflects recipient delivery evidence. unknown
must remain visibly uncertain. This is the latest historical account action, not
necessarily a send for the currently linked generation. On unlink, phone_last4 is
null and linked false; explicit saved preferences and historical delivery remain.
Return no full phone, source/result text, account IDs, challenge/hash, worker IDs,
attempt tokens or secrets. The query uses one statement snapshot. Database errors
propagate; do not replace them with disconnected/default success state. Caller
identity must come from verified auth, never a model or arbitrary request body.

Existing Settings now includes optional whatsapp_business_number (environment:
AGENT_WHATSAPP_BUSINESS_NUMBER), default None, validated 7–15 digits with nonzero
first digit, no plus/spacing. This is a PUBLIC destination number, distinct from
Meta's internal phone_number_id. No guessed/default number is configured. This is
shape validation, not proof the business owns/configured the number.

Murtazo owns authenticated GET /v1/whatsapp assembly, public configuration/readiness
fields, proxy allowlist and student controls under #17. No app/frontend endpoints
are added here. No migration, connection authorization or sending permission is
introduced. Approved-template policy/configuration remains a separate Codex-owned
shared-contract task; expired-window delivery stays held.
