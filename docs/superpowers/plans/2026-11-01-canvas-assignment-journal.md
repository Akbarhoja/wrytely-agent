# Durable assignment ingestion implementation plan

> **For agentic workers:** Use superpowers:executing-plans with TDD and one fresh whole-branch review.

**Goal:** Send mapped assignment evidence through the existing paired journal and academic API without losing captured pages on suspension/network loss.

**Architecture:** Reuse unchanged #60 mapper and existing journal/lock/lease/receipt recovery. Journal v2 adds one active assignment progress record; strict v1 migration preserves all existing captured intents. A small helper maps bounded raw/already-extracted assignment inputs into exact C2 wire items and revalidates stored payloads. No second storage or runtime.

**Spec:** [#113](https://github.com/Akbarhoja/wrytely-agent/issues/113), implemented C2v1 and #112 academic HTTP. Base `7d400010`; branch `codex/canvas-assignment-journal`.

## Constraints

- M-owned extension/tests/scoped docs only; unchanged #60 helper/test/history reuse. No app/shared/contracts/CI/STATUS/cross-layer edits.
- One existing operation lock; persist before POST, validate acknowledgment and persist before result. Credentials/leases stay private.
- Validated legacy v1->v2 migration must preserve keys/bodies/renewal and refuse unsupported or corrupt old state.
- Assignments only in this increment; other required academic kinds/long-document wire remain follow-ups. No source fetch/parser/host/scheduler/install/live/provider call.
- 50 items/page,1MiB envelope,2MiB input,100 pages/5000 items/resource,10000 global checkpoint sequence,8MiB journal/finish reply.
- Bind course/item/extracted identity, normalized title300/content24000, exact reference/fields and portable canonical payload. No clipping or default active/permission assumptions.
- Preserve source/account/scope/expiry fences and partial/historical evidence. No false complete resource/scan or source promotion.

## Task 1 — assignment wire helper

- [x] Write binding/mapping/normalization/limit/corruption tests; run RED for missing module.
- [x] Implement helper using existing mapper/canonicalizer and strict stored-payload revalidation; expect focused tests pass.

## Task 2 — journal and academic transport

- [x] Extend existing M journal fixture for academic receipts and write RED tests for missing methods, migration, replay/resume/partial/invalid receipts/controls/locking.
- [x] Add commitAssignmentPage/finishAssignmentResource to the same private operations and lock; route academic POSTs through current trusted transport. Implement resource-aware expected checkpoints and receipt parity; preserve discovery behavior.
- [x] Run all Node suites, required Ruff/format/full disposable backend (including ten actual old HTTP scenarios), web/TypeScript and formatting/diff checks.
- [ ] Fresh review and one verified fix pass if needed; publish draft PR/evidence and request counterpart/CI/STATUS handoff.

## Review focus

- A pending accepted academic page may advance server checkpoint before a lost acknowledgment; resume must reconcile that exact page and no other advancement.
- Legacy pending course/finish/resume intents survive migration with identical keys and payloads.
- Missing/duplicate/changed observation/source-version receipts cannot advance local progress or close a resource.
- An incomplete/historical early page remains incomplete across a later terminal page.
- Resource progress is per selected assignment resource, bounded and sequential, not overwritten by global course counts.
