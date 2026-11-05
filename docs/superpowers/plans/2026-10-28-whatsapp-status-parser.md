# WhatsApp status parsing implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline.

**Goal:** Parse authenticated provider delivery evidence without trusting account IDs
from recipients or interpreting provider acceptance as delivery.
**Architecture:** Add a transport-local immutable status record and pure parser to
the existing adapter module. No storage or webhook assembly until the reviewed
delivery contract is available. Existing raw-body signature verification remains
the caller's prerequisite.
**Tech stack:** Python 3.12, datetime, pytest; no new dependencies.
**Spec:** `docs/stages/B1-murtazo.md`, issue #4 agreement, issue #5 claim.

## Global constraints

- Only the configured business account, phone number and messages field qualify.
- Parse sent/delivered/read/failed evidence; never derive aggregate delivery state.
- No shared files, database client, live calls or model calls.
- Reject missing, malformed or excessively future timestamps; cap accepted slight
  future skew at injected UTC now (five-minute maximum skew).
- Preserve original integer provider epoch alongside the capped event time.

## Review focus

- Wrong business/phone must never produce evidence.
- Missing/malformed fields must not crash processing a mixed batch.
- Unknown statuses must not create delivery evidence.
- Delayed events retain their event time; receipt time cannot replace it.
- Malformed timestamps, including huge numbers and booleans, must fail closed.

## Task 1

Files: `integrations/whatsapp.py`, `tests/test_whatsapp.py`.
Produces `extract_statuses(payload, *, phone_number_id, business_account_id, now)`
returning immutable records: provider_id, recipient, status, provider_timestamp,
event_at, business_account_id, phone_number_id. Account scope comes from configured
envelope matching; recipient alone never establishes student identity.

- [x] Write mixed-batch, identity filtering, malformed envelope, supported status,
  old timestamp, future-skew, immutability and missing-configuration tests.
- [x] Run focused tests and observe missing-parser failure.
- [x] Implement bounded field validation and safe envelope traversal.
- [x] Run transport tests, full backend regression suite with isolated Postgres,
  lint, format and diff checks. Record unresolved setup blockers honestly.
- [ ] Update development notes and post exact validation evidence to #5.

## Execution record

- Akbar confirmed transport/parser ownership in #4 and #5; Murtazo confirmed the
  storage clarification in #4 comment 6481199754. Typed storage PR is pending.
- Portable official EDB PostgreSQL archive is downloading into ignored `.tools`.
- RED: 27 new parser tests failed for missing extract_statuses; 24 prior tests passed.
- GREEN: 51 transport tests pass; full suite 118 passed against isolated Postgres.
- Ruff lint/format and git diff checks pass. No shared files were changed.
- Typed storage interface agreed in #4 comment 6481281451 for dependent text wiring.
