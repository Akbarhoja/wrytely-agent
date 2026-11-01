# Canvas host foundation implementation plan

> For agentic workers: use superpowers:executing-plans inline, with one fresh final reviewer.

**Goal:** Add an inactive private browser host over the existing Canvas client.

**Architecture:** Separate persisted controller preferences from Chrome listener
registration. Keep existing pairing credentials and discovery journal authoritative.

**Tech stack:** Native ES modules, Node test runner, Chrome storage/alarms/runtime.

**Spec:** [Host specification](../../stages/P1-CANVAS-HOST-FOUNDATION.md).

## Global constraints

Claim #136; six new files only, branch codex/canvas-host-foundation from00dad2ac.
No activation, account/provider calls, UI, packaging, shared stores or schema edits.
No source/credential data in replies. Default disabled; explicit enable/pause.

## Review focus

1. Storage failure during pause must not falsely claim durable pause.
2. Late completion must not override a newer control epoch.
3. Worker recreation must respect cooldown without duplicating source journals.
4. Pairing and unknown errors must not be retried as generic network failures.
5. Content scripts and forged messages must never trigger collection/control.

## Task 1: Controller

Files: host.mjs, host.test.mjs, this plan and scoped stage evidence.
Interface: createCanvasHost({apiOrigin,canvasOrigin,storageArea,alarms,client?,now?,randomUUID?})
returns status/enable/disable/collect/pair/bind/reconcile methods. Production default
client is createPairingClient with the same storage area.

- [x] Write focused controller tests, run node --test extension/canvas-pairing/host.test.mjs.
      Expected: missing-module failure before implementation.
- [x] Implement private preferences, serialized controls, epoch fence, bounded
      client operation, controlled projection and persistent cooldown.
- [x] Verify default inactivity, restart, lost alarms, pair/bind, partial coverage,
      pause races and storage failures. Expected: all focused tests pass.

## Task 2: Chrome event adapter

Files: host-events.mjs, host-events.test.mjs.
Interface: registerCanvasHost({chrome,apiOrigin,canvasOrigin,...}) returns host,
ready reconciliation promise and dispose for worker-recreation tests.

- [x] Write strict sender/message and listener lifecycle tests. Run focused file.
      Expected: missing-module failure.
- [x] Implement synchronous registration, async sendResponse, exact message shape,
      named alarms and idempotence. Expected: focused tests pass.
- [x] Run all extension Node tests; Ruff check/format and full pytest with disposable
      Postgres. Expected: no failures; distinguish baseline from new host coverage.
- [x] Fresh final review, address important findings with regressions, document
      evidence and limits. Delivery instruction: commit six files, draft PR and request
      A review/status row; external records follow the verified implementation.

## Execution ledger

Base00dad2ac. User repeatedly requested determine-and-act; existing scope determines
this inactive foundation. Popup/package/live browser acceptance remains separate.

Task 1: controller tests RED missing module, then GREEN; epoch-before-dispatch
and pairing/enable regressions each observed RED then GREEN. task-done helper
ran controller tests successfully; its local ledger range is base..base because
files remain uncommitted until required checks complete.

Task 2: event tests RED missing module then GREEN. Final focused24/all389 Node
pass after review fixes. Ruff check/format178 pass. Required full backend:
966 passed/no skips/two existing warnings in1377.77s on fresh disposable Postgres.

Final review: fresh read-only reviewer, six untracked files against base00dad2ac;
reviewed before commit while the required backend suite ran. No code changes since
review except the two review fixes and the tested author-audit fix below.
Final commit will preserve this reviewed-and-corrected implementation.

Final: fixed real collector string coverage mismatch — partial/complete regression
observed RED then GREEN, final all389 extension tests pass.

Final: fixed identity rejection false disabled flag — regraded important because
it could mislead a user about collection. Regression observed RED then GREEN;
final all389 extension tests pass. No deferred minors.

Final: fixed author-audit completed-step running status — observed RED then GREEN,
final all389 extension tests pass. The busy lock still spans the entire step;
only the completed reply projection changes. No additional reviewer was dispatched.

Final: Ruling: installed MV3 termination/alarm/sender behavior, live collection,
UI/package and continuous operation remain explicit future acceptance, as the
reviewer set aside. Cost if wrong: these tests cannot substantiate an operational
installed product. Backend verification and fresh GitHub state are checked by the
author separately rather than inferred from the reviewer.
