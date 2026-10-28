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
