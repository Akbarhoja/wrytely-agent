# M2 combined review checkpoint

Work #35; branch codex/m2-integration-review. Executable merge 0d47e40 combines
Murtazo's published #28 checkpoint 5473d46 with #34 corrected at db241ab. This is
a separate review candidate, not a protected-main merge, release or deployment.
No teammate implementation was rewritten.

## What is combined

- Authenticated immutable snapshot create/list/detail and student context screen.
- Private responsibility/artifact/check reads and result screens with honest stale,
  missing and failed check states.
- Standalone private-draft confirmation component; deliberately not mounted and
  without transport in this checkpoint.
- Atomic bound responsibilities, private-draft intent, source-policy/rubric
  assessment, planner routing and checked-draft/recovery runtime.
- Base PlannerDecision nonblank validation restored after Murtazo's review finding
  #34 comment6509066599. Seven regressions observed three failures before fix and
  all seven passing after; DraftPlannerDecision inherits the base validator.
- Explicit UTF-8 synthetic-fixture read for Windows portability.

## Evidence and limits

Exact executable head 0d47e40 CI40967993517 reports foundation and web success.
Local combined checks:94 frontend tests, TypeScript, Prettier, webpack production
build, Ruff lint/format, diff checks and26 focused non-DB tests pass. Full database
tests were not run locally because sandbox process/shared-memory setup is blocked.
Do not report a locally reproduced full backend count. CI logs could not be
downloaded in this review (signed log download403); job success metadata was read.

Snapshot/result code was reviewed for verified ownership, no-store/error behavior,
UUID allowlisting, retry identity, untrusted text rendering, account/selection
fencing and readiness/stale distinction. Frontend tests use simulated responses;
they are not actual Clerk/backend or Meta acceptance. No live provider call,
message, source authorization, business setup or migration application occurred.

## Exact remaining consumer boundary

Akbar explicitly kept final delegation wiring with Murtazo. Codex must not take
over those app/web files. When the owner next works, the existing private
confirmation component needs a narrow authenticated POST consumer of
create_draft_responsibility and a private status consumer of
draft_responsibility_status, as documented in CONTRACTS.md. Server owns identity,
budgets and source policy; client provides explicit private-only confirmation,
objective, selected owned source IDs and stable retry identity. Do not accept
client CoursePolicy, readiness, task IDs or model assessments as authority.

The component must not be mounted as working drafting until transport, consent,
error/isolation and status behavior pass. Current saving/viewing source/result
screens cannot request a draft. Existing analysis keys cannot upgrade to draft
mode. Result viewing never shares, sends or submits work.

After owner integration: test the full student path with synthetic context and
scripted providers first, then a bounded real Meta M2 run after confirmed scope.
Finish disclosure-format and deterministic numeric-rubric/word-limit gaps, preserve
source evidence, verify autonomous continuation rather than operator-selected
steps, and record saved result versus actual message delivery separately.

Migration009 is present in the candidate but has NOT been applied to retained
development services. No008/A4 is included. M1 delivery/business restrictions and
remaining live controls are open; M2 live acceptance is not complete. Main still
requires independent human approval. Teammate's scheduled tasks were previously
asked to be deleted; no scheduler was created or restarted by this session.
