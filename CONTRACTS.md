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
