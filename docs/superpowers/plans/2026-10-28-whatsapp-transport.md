# WhatsApp template transport implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the existing WhatsApp adapter with single-attempt body-text templates.
**Architecture:** Keep transport in `integrations/whatsapp.py`. Reuse `DeliveryResult`
and the existing HTTP evidence classification; policy and durable state remain above
the adapter and wait for agreement in issue #4.
**Tech stack:** Python 3.12, httpx, pytest, Ruff; existing locked dependencies.
**Spec:** `docs/stages/B1-murtazo.md`, `docs/stages/B1b-whatsapp.md`; claim #5.

## Global constraints

- No runtime/shared/schema changes, live sends, or production configuration.
- A template request does not prove approval, permission, or delivery.
- Never retry an ambiguous send automatically.
- Transport supports body text parameters only in this increment.

## Review focus

- Malformed template identifiers must fail before HTTP.
- Invalid recipients must fail before HTTP.
- Missing/blank/overlong body parameters must fail before HTTP.
- Timeout and malformed success remain unknown, with one request at most.
- Existing text-send behavior must remain compatible.

## Task 1: Template send transport

Files: `integrations/whatsapp.py`, `tests/test_whatsapp.py`.
Interface: `WhatsAppAdapter.send_template(*, recipient: str, name: str,
language: str, body_parameters: tuple[str, ...], action_id: UUID) -> DeliveryResult`.
Caller must select a configured approved template and matching parameter schema.

- [x] Write tests for the exact template payload, no-component static templates,
  invalid input without HTTP, provider evidence, and lost-response single attempt.
- [x] Run `python -m pytest tests/test_whatsapp.py -q`; observe missing-method failures.
- [x] Implement `send_template`; share single-attempt request/result handling with text.
- [x] Run focused tests, full backend suite, Ruff lint/format and diff checks.
- [x] Record actual results and blockers in the work item and setup documentation.

## Deferred integration

Durable claim/authorization/result recording, callback persistence, preferences,
conversation-window enforcement and template allowlisting depend on the owner's
agreement in #4. No substitute database layer will be created.

## Execution record

- Python 3.12 local virtual environment created; `uv sync --locked` succeeded.
- Claim posted: https://github.com/Akbarhoja/wrytely-agent/issues/5#issuecomment-6481056367
- Interface request: https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6481060467
- RED: 14 new tests failed because `send_template` did not exist; 10 existing passed.
- GREEN: 24 transport tests pass. Full run: 46 passed, 45 database-fixture setup errors.
- Database regression gate remains open: no isolated Postgres is installed/configured
  on this Windows machine. No production/existing account database was used.
- Ruling: execute the already-authorized handoff increment inline, preserving shared
  ownership; defer worker contracts and callback persistence until issue #4 agreement.
- Continuation: isolated Postgres configured; all 118 backend tests now pass,
  including 51 transport tests after parser increment. Two existing warnings remain.
