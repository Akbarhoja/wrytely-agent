# Internal academic workflow validation — October 29, 2026

Work item: [#26](https://github.com/Akbarhoja/wrytely-agent/issues/26).
Base: codex/m1-integration at 6accd71. Test branch: codex/m2-internal-validation.
Scope: tests, synthetic fixtures and documentation only; runtime behavior unchanged.
This is internal A2/A3 evidence, not live M2 acceptance or a completed academic agent.

## What ran

The new tests use the real Store, planner, worker, drafting helper, verification
and disposable local Postgres. Only model responses are scripted. No vendor keys,
real academic records, connected school systems, paid requests or messages are used.
The fixture contains the scenario's four fictional observations and a hand-written
266-word comparison body. It is not model-generated research.

| Exercise | Observed result | What this establishes |
|---|---|---|
| Internal multi-step flow | Two academic steps and three planning episodes complete with new Store instances | Saved analysis reaches later planning; checked-draft result reaches reassessment |
| Mandatory review/revision | First review fails, second draft passes; both artifacts and reports persist | Failed review cannot silently become a successful result; feedback reaches revision |
| Interrupted review | Review exception leaves a saved unready draft; next attempt reviews that same artifact and finishes | Recovery does not repeat saved preflight/generation or duplicate the artifact |
| Fabricated quotation | Two bounded draft attempts stay unready and block the duty | Exact-quote failure prevents readiness and blind continuation |
| Other student's evidence | Private marker excluded from model context; task/artifact lookup denied | Runtime storage/context boundaries preserve account ownership |
| No external action | No WhatsApp outbound row; internal work excluded from normal chat messages | Completing academic analysis does not authorize delivery or impersonate student chat |
| Separate disclosure only | Rejected with disclosure_missing_from_body | Current behavior conflicts with the scenario's separate-disclosure formatting |

The continuation decisions, draft text and semantic verdicts are predetermined.
These tests do NOT establish that Muse Spark will choose useful work, interpret
policy correctly, write good prose or assess factual support reliably. The test
operator configures the academic drafting task explicitly after planning selects
it; this is not proof of automatic student-facing delegation. Store reconstruction
and a caught review exception are not an operating-system process-kill exercise.

Full backend suite: 263 passed, two existing warnings, in 9.05 seconds. Ruff
lint/format and diff checks pass. Recovery negative control: in an isolated
interpreter, discarding draft_progress checkpoints caused the recovery test to
fail because the task remained ready instead of completing. The control did not
modify production files; the normal full suite passed without that mutation.

## Current interface handoff for Murtazo

These are existing Python boundaries, not newly exposed HTTP endpoints. Student
identity always comes from verified Clerk/session or verified channel mapping.

1. Provision with Store.provision(verified_user_id), reusing the existing agent.
2. Ingest each SourceObservation through Store.observe_source. Preserve stable
   keys, upstream revisions, aware retrieval times, evidence references and honest
   coverage. Manual uploads are snapshots. Store returns version id and source_id.
3. After explicit responsibility delegation, create_responsibility(user, objective,
   idempotency_key) and bind_source(user, duty_id, source_id) attach private context.
   The initial planning task must not run before required bindings are complete.
4. The existing worker/planner creates an academic task. Trusted assembly calls
   configure_drafting_task(user, task_id, policy=CoursePolicy, rubric=list[RubricItem],
   max_revisions=...) only after explicit drafting authorization, while the task is
   ready, unattempted and current. Policy/rubric quote actual bound version IDs.
   Same request is idempotent; changed configuration conflicts. An active task
   cannot be upgraded to drafting.
5. runtime.worker.run_once reuses generate_checked_draft: policy preflight, saved
   review artifact, mandatory check, bounded revisions. On success, task result
   contains state=ready_for_review and artifact_id, and responsibility planning
   resumes. A blocked check blocks the task/duty rather than claiming completion.
6. Store.artifact(verified_user_id, artifact_id) retrieves the private artifact with
   stale status; None means absent/not owned. The existing web proxy does not yet
   expose artifact/report retrieval. Murtazo owns that app/UI assembly after the
   response/error contract is agreed. Do not expose the internal readiness commit.

No supplied source, model output or browser user ID may authorize actions. No
artifact state grants permission to share, submit or send a WhatsApp message.

## Gaps found before live integration

### Safe delegation and task routing

create_responsibility immediately queues a planning task. Sources bound only after
work starts can invalidate the responsibility. Separately, configure_drafting_task
must run before an academic task's first claim, while a continuous worker may claim
it immediately. Manually stopping workers makes this test deterministic; it is not
a viable multi-user product routing strategy.

Before B2 assembly, agree how trusted source binding and delegated-drafting intent
become available atomically before the relevant worker claim. Codex owns any
needed shared-store/runtime change; Murtazo owns its authenticated API/connector
consumer. This document proposes a requirement, not an agreed new payload or a
completed fix. Do not implement a competing planner or poll-and-upgrade race.

### Disclosure formatting

The scenario asks for disclosure outside the word-counted body. The current
disclosure_required verifier requires its text inside body, and generation prompts
also request that. The happy-path test therefore includes it in both body and
disclosure, and a separate negative test records the incompatibility. It does not
weaken the policy to permitted to make separate disclosure pass. Resolve the
display/counting contract before the live scenario; no policy change was made.

### Deterministic requirements and semantic checks

The saved fixture meets the scenario word range, but the runtime does not extract
numeric limits or deterministically enforce them from a RubricItem quote. A
positive scripted semantic assessment is not proof of word-limit enforcement.
Required source coverage and disclosure sufficiency also need precise policy/
rubric interpretation in the integrated product. Automatic extraction is not
implemented by these tests. Do not label this validation as a full rubric engine.

### Student experience and actual autonomy

Commitment extraction, the delegation question, source binding, safe draft routing,
private artifact/check presentation and live source coverage still need integrated
proof. Those product paths are not replaced by this direct Store setup. The group
message is a fixture, not evidence of live Teams ingestion. Next live exercise must
use Meta within an explicitly bounded scope, observe useful self-directed steps,
and deliver an inspectable result through the agreed student experience.

M1 WhatsApp account restrictions and remaining live acceptance are unchanged.
A4, requirement-change revision and follow-up remain parked. No public release,
production migration or deployment is authorized by these internal checks.
