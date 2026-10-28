# WhatsApp text delivery worker plan

> **For agentic workers:** Use superpowers:executing-plans inline.

**Goal:** Connect the agreed Store delivery ledger to the existing transport and
signed webhooks without enabling proactive templates or hiding uncertain sends.
**Architecture:** Stack on complete #9/#7 dependencies in this feature branch;
never merge shared branches. `integrations/whatsapp_delivery.py` owns one-attempt
orchestration. `app/main.py` owns private preferences and signed callback/time
assembly. `app/whatsapp_worker.py` owns process lifecycle with zero-retry httpx.
**Spec:** B1-murtazo handoff and CONTRACTS.md delivery storage section; interface
agreement recorded in #4 comment 6481281451. **Stack:** existing Python/FastAPI/Store.

## Global constraints

- Shared storage/schema changes remain Akbar's; reuse DeliveryClaim and Store.
- Dispatch only the authoritative payload from one fresh authorization.
- Never replay authorization, reclaim unknown, or retry after ambiguous dispatch.
- Reject invalid signatures before interpreting messages/statuses.
- Explicit preferences and trusted event time are mandatory for eligibility.
- Expired window stays held as approved_template_required.

## Review focus

- Death after network dispatch but before persistence must not cause resend.
- Pause/unlink or stale lease before authorization must prevent network IO.
- Callback-before-response and replay must use exact account/recipient/reference.
- Old/delayed inbound messages cannot reopen a conversation window.
- Invalid preferences or caller-supplied account IDs cannot affect other students.

## Task 1: One-attempt orchestration

Files: integrations/whatsapp_delivery.py, tests/test_whatsapp_delivery.py.
Interface: run_once(store, adapter, *, worker_id, business_id, phone_number_id) -> str.
- [x] Test real Store with HTTP MockTransport: accepted, lost response, post-send
  storage interruption, pause/unlink, expired window, duplicate worker/restart.
- [x] Observe failures, implement one claim -> authorize -> one send -> record.
- [x] Run the task's tests and integrated suite.

## Task 2: Signed callbacks, event time and private preferences

Files: integrations/whatsapp.py, app/main.py, tests/test_whatsapp_flow.py.
- [x] Test signed statuses, invalid signature, replay/late callback, callback before
  response, original provider timestamp after durable ingestion, and two-account
  private preference validation.
- [x] Extend WhatsAppText with optional event_at; absent/invalid timestamp never
  acquires eligibility. Map transport status to the shared typed event using its
  original epoch for stable replay identity.
- [x] POST /v1/whatsapp/preferences: strict explicit consent, IANA timezone and
  integer quiet-hour bounds; derive account from verified session; reject extras.
- [x] Run API/messaging tests and full regression suite.

## Task 3: Process assembly and evidence

- [x] Wait for requested shared token/version settings in #4; do not duplicate config.
- [x] Construct Store and zero-retry httpx from explicit settings; poll with bounded
  waits and stop cleanly on interrupt. No automatic database migration or live test.
- [x] Verify lint/format/diff and full backend tests against disposable Postgres.
- [x] Record evidence, remaining template/live limits and dependency order in #5.

## Execution record

- Consumed complete #9/#7 dependency chain and shared config commit bd944f8 in
  this feature branch only. Shared branches and production systems unchanged.
- RED: six worker tests, three API tests, and two process tests failed for missing
  behavior before implementation. Added fault/isolation cases after those passed.
- GREEN: 172 backend tests pass on isolated password-protected local Postgres 17;
  Ruff lint/format and diff checks pass. Two existing warnings remain.
- Independent static review found no Murtazo-owned actionable defects. Akbar also
  reviewed the exact PR head and independently validated offline compatibility.
- Shared-owner orphan-capacity fix `d61217b` consumed by dependency merge `068210b`.
  No shared code was rewritten in Murtazo's scope. Updated full suite: 175 passed,
  two existing warnings; Ruff lint/format and diff checks pass.
- Templates remain held outside 24 hours; live Meta/WhatsApp evidence unavailable.
