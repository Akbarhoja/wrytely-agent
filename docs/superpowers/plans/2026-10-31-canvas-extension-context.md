# Canvas extension context implementation plan

> **For agentic workers:** Use superpowers:executing-plans and test-driven-development.

**Goal:** Connect the existing paired extension client to the agreed current-context Store method through strict private HTTP assembly.

**Architecture:** Reuse #64/#52/#70 on accepted A #84 without replacing modules. POST `/v1/source-connections/canvas/context` accepts origin-only JSON and the current ingestion bearer. `readCurrentContext()` obtains a bounded, validated context, stores the refreshed safe connection, and returns only safe scope/discovery metadata. It does not verify the current Canvas browser account, grant collection, or bypass generation/scope checks on later sync.

**Tech stack:** FastAPI, existing Store/Postgres, JavaScript Node tests and trusted-context extension storage.

**Spec:** [Claim #91](https://github.com/Akbarhoja/wrytely-agent/issues/91), implemented C1 context in CONTRACTS.md, P1-M1 work order.

## Constraints and review focus

- Base accepted A `581a9f5`; reuse original M #64/#52/#70 commits as `9d631b4`, `14c29bb`, `e711e66`. No shared/contracts/runtime/STATUS/dependency/CI edits.
- New edits only app/source_connections.py, tests/test_source_connection_api.py, extension/canvas-pairing/client.mjs and its test, plus this plan and scoped handoff.
- API uses existing 16KiB strict-body/no-store wrapper; no session token, posted user/connection ID or query can select ownership. Missing/expired/revoked/re-paired bearer and wrong origin yield controlled 401. Unsupported query/JSON fields yield redacted 422.
- Client preserves HTTPS exact-origin, trusted-context storage, omit credentials, no-store, redirect rejection, timeout and one upstream attempt. Context responses bounded at64KiB; existing lifecycle stays16KiB. Support all1000 course IDs (1–20 positive ASCII digits),9 unique resource kinds, both scope modes and five discovery coverage values.
- Exact connection match, monotonic cached generation, nonnegative safe integer scope revision, valid date strings and unexpired credential. Project only known fields; no bearer, subject or arbitrary nested source data returned.
- Read/format failures retain valid pairing but return no context.401/expiry removes local credential. Storage failures must not return unpersisted context. Context is a snapshot, never a sync lease or current-provider-account proof.

## Task: HTTP and client context handoff

- [x] Write API and client tests; observe missing-route/method RED.
- [x] Add the route and client projection using existing helpers; focused tests GREEN.
- [x] Verify real Store-backed pending/connected/two-account/scope-generation/revocation cases and client malformed/large/error/storage boundaries.
- [x] Run required Ruff check/format/full disposable backend, Node suites, existing web/typecheck and formatting/diff checks.
- [ ] Obtain read-only review; publish draft PR and request A counterpart review with exact evidence and limits.

## Execution record

Claim #91/#4 comment6547866499 recorded before edits. Existing isolated worktree reused; PR90 preserved. No live access or browser change. Recurring automation remains deleted.

RED14 API/25 new Node failures, initial GREEN35 API/78 Node; two expiry regressions separately RED then GREEN. Final80 Node/probe passed, full632 backend passed with two existing warnings in344.11 seconds, full114 web passed in31.37 seconds, TypeScript/Ruff/formatting/diff passed. Read-only reviewer independently ran79 Node cases, found one Store-expiry-response cleanup mismatch, then independently verified its new regression (one pass) and confirmed the fix. No Python change after the full backend began; final Node suite rerun after the review fix. Existing CI covers backend/web, not extension Node; request that owned CI addition from A. Counterpart acceptance and remote CI remain separate gates.
