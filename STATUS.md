# Engineering status

Started October 27, 2026. Supervisor: Akbar. Lead: Codex. Engineer: Murtazo.

## Current integration checkpoint — October 28

Feature expansion is paused by Akbar. `codex/m1-integration` combines runtime #16,
Murtazo delivery/onboarding #20 and template contract #22; A4 #24 is excluded.
247 backend and 44 frontend tests pass together; Ruff, Prettier, TypeScript and
Next build pass. No live connection is verified. Current backend process has none
of the required development credentials configured. Akbar requested help setting
up the Meta app/test number first; no live budget authorization is assumed.
See docs/M1-ACCEPTANCE.md. Required independent review precedes protected-main
merge. The chronological entries below describe branch history, not completion
of live milestones. Template worker opt-in remains pending and sends stay held
outside the window. Existing production remains unchanged.


| Stage | Owner | State | Evidence / remaining work |
|---|---|---|---|
| P0 existing-service inspection | Codex | partial | Existing product uses Clerk Next.js 7, Neon/Postgres, S3-compatible storage; no production changes. Live account configuration pending. |
| S0 foundation | Codex | in review | Isolated repo, scoped Postgres migration, auth verifier, provisioning, durable queue, bounded Meta adapter and API. Offline tests against real local Postgres pass. |
| A1 task/worker foundation | Codex | in review | Attempts fenced, same-agent concurrency controlled, pause/restart behavior tested. Stateful episode resumption implemented locally; full responsibility planner still to build. |
| B1a signed-in frontend | Codex scaffold; Murtazo live integration | scaffold in review | Next.js workspace, Clerk routes/provider, authenticated same-origin API boundary, persisted retry keys, task status and pause controls. Live two-account checks pending. Akbar will invite Murtazo. |
| B1b verified messaging | Murtazo | partial scaffold | Codex prepared adapter, linking, inbound task storage and reply outbox. Murtazo owns remaining delivery, web controls and live integration. |
| M1 live round trip | Both | not achieved | Need isolated database configuration, existing Clerk instance public verification configuration, Meta development key, frontend and messaging integration. |
| M2 academic ownership | Codex + Murtazo | internal planner implemented locally | Duties select bounded internal steps and continue from saved results. Source context ingestion, commitments, verified artifacts and student-facing delegation remain pending. |
| M3 public pilot | Both | not started | Usage budgets, connectors, controls, external-action gateway and integration evidence required. |

No live Meta or Clerk call has been verified. No public signup or deployment is
enabled. No customer database migration was applied. The current model tests are
scripted provider responses against a real disposable Postgres store. Web tests
use injected sessions and simulated HTTP responses. Public-shell browser checks
do not establish a live authenticated round trip.

The GitHub repository is now public at Akbar's request. The application itself is
not deployed publicly. Existing Wrytely production configuration is unchanged.

Current local verification: 44 backend tests against disposable Postgres and 24
frontend boundary/interaction tests pass. Ruff, Prettier, TypeScript and the Next.js
production build pass. Browser checks cover 1440px desktop and 390px phone views,
connection navigation and no horizontal overflow. Main branch protection is verified
as described in TEAM.md. Live provider integration remains unverified.

The default student screen is now a work overview, with conversation as a separate
view. Its account-scoped task list reads the latest 50 real records and refreshes
without opening chat. No sample course work or decision requests are populated.
Current saved tasks are conversation tasks; academic responsibility ingestion,
decision requests and autonomous course workflows remain future implementation.

October 28 continuation: B1b WhatsApp adapter preparation is implemented locally:
raw-body signature validation, business/number filtering, text extraction and a
single-attempt sender with accepted/failed/unknown outcomes. Ten new offline tests
pass. No live WhatsApp request was made. No webhook route or automatic sender is
enabled; durable linking, inbound deduplication, outbound storage, status callbacks
and template/window enforcement remain required. DBOS is still a proposed bounded
trial, not an adopted dependency.

Validation for this continuation: all 54 backend tests pass against disposable
local Postgres; Ruff lint and formatting pass. Dependency lock updated. Existing
24 frontend tests were not rerun because no frontend code changed.

October 28 B1b continuation: development webhook routes and authenticated
link/unlink APIs now persist single-use expiring challenges, verified numbers,
unique inbound provider IDs, text tasks and a transactional reply outbox. Link
secrets do not enter model context. Unlink cancels pending delivery and relinking
does not redirect old work. Migration 002 is local-only; existing migration 001
is unchanged. A concurrency test exposed a pre-existing task-claim race; a fresh
active-lease check under the agent lock now prevents overlapping worker claims.

Validation: 62 backend tests pass against disposable local Postgres; Ruff lint,
format and diff checks pass. No frontend files changed. No live credentials,
WhatsApp sends or production migrations were used. Delivery worker, web linking
controls, delivery callbacks and template/window enforcement remain unfinished.
Development setup is documented in docs/stages/B1b-whatsapp.md.

October 28 runtime continuation (Akbar/Codex ownership): task episodes now replay
saved model turns and tool results across worker attempts. Pending read-only tool
calls finish before the next model turn. A saved final answer can be committed
without repeating inference after an interruption. Replay is scoped and fenced to
the current task/agent, including Meta encrypted reasoning blocks. Episode turn
limits and maximum attempts still apply. No new model/provider service adopted.

Validation: 67 backend tests pass on disposable local Postgres, including five new
resumption tests using abrupt-termination simulation and fresh Store instances.
Ruff lint, format and diff checks pass. This is not an OS process-kill test or a
live Meta smoke test. External side effects require their own durable action
ledger; replay alone does not ensure exactly-once sending. Full autonomous
responsibility planning and academic source memory are still pending.

October 28 A2 runtime continuation: responsibilities and internal planning tasks
are persisted by migration 003. Explicit trusted delegation creates a planning
job; the model chooses one internal step, its saved result triggers reassessment,
and the loop stops at completion, blockage or a bounded step limit. Duties and
history are account-scoped. Planning decisions recover across attempts. Internal
prompts/results are excluded from ordinary student conversations. No Murtazo-owned
app, frontend, messaging or source adapter files changed in this stage.

Validation: 77 backend tests pass on disposable local Postgres, including ten new
planner tests. A scripted model selects three useful steps over seven separate
worker runs with no new external input; prior results reach later planning turns.
Tests also cover idempotency, isolation, pause, duplicate steps, budget exhaustion,
blocked duty fairness, saved-decision recovery and rollback without orphan tasks.
Ruff lint/format and diff checks pass. This proves orchestration with scripted
responses; autonomous planning quality and Meta tool-schema compatibility are not
live-validated. Migrations remain local-only. API/UI delegation, course-policy
handling, source retrieval, verified artifacts and requirement changes remain
unfinished. DBOS is still not adopted.

October 28 — issue #6 academic memory implementation prepared for review on
codex/academic-memory. Migration 004 adds immutable source versions, explicit
responsibility/source bindings, exact-quote evidence and memory revisions. Planner
context now includes bounded private excerpts, provenance, source coverage,
retrieval timestamps and stale/truncated indicators. Changed evidence invalidates
active tasks and fences old worker writes; old evidence remains auditable.

Validation: 89 backend tests pass against disposable local Postgres; Ruff lint,
format and diff checks pass. Twelve new tests cover idempotent/conflicting/late
observations, timestamp validation, isolation/binding limits, quote checks,
source-change fencing, bounded excerpts, restart persistence and planner context.
No live provider call or production migration occurred. No Murtazo-owned app,
frontend, connector or WhatsApp files changed. The connector contract is a draft
pending agreement in #4. Source ingestion is not exposed to students yet. Semantic
claim verification, model-driven fact extraction and automatic requirement-change
revision remain unimplemented. Issue #6 is awaiting review, not marked done.

October 28 — issue #8 delivery storage prepared on codex/delivery-storage, stacked
on academic-memory PR #7. Adds migration 005, typed fenced delivery claims,
one-time send authorization, conservative preference/window holds, private consent
and quiet-hour storage, current-link generations, trusted inbound event-time
storage and replay-safe status evidence with early-callback reconciliation.
Murtazo retains transport/parser/worker/API assembly and messaging tests.

Validation: 106 backend tests pass locally against disposable Postgres; 17 new
storage tests cover concurrent claims, one-time dispatch authorization, controls,
expired windows, unknown attempts, relinking, wrong callback scope, callback/result
races, orphan reconciliation and private preferences. Required Ruff/diff checks
run before review. No live provider calls, source connections, production schema
changes or app deployment. Template payload/configuration support is not implemented;
expired-window sends stay held as approved_template_required. No M1 live milestone
is claimed. Typed contract awaits Murtazo review before dependent assembly.

October 28 — issue #10 A3 first increment: private saved draft artifacts with a
mandatory finalization/check boundary, prepared on codex/artifact-verification.
Migration 006 is stacked on delivery-storage #9 and memory #7. Drafts stay review
until deterministic source/policy/citation checks and separate model-assessed
claim/rubric/policy/disclosure checks pass. Reports and usage persist. Source
changes and pause during assessment fence the final readiness write.

Validation: 126 backend tests pass on disposable local Postgres, including twenty
new artifact tests. Required Ruff lint/format and diff checks run before review.
Offline scripted assessments verify gating and persistence, not live Meta judgment
quality. No Murtazo-owned app, frontend, transport or connector files changed.
No live inference, sends or production migrations occurred. This is not complete
A3: generation/tool wiring, automatic policy/rubric extraction, student review APIs,
sharing and full integrated workflows are still pending. A4 revision remains future.

October 28 — #12: internal draft-generation helper now connects source/policy
preflight, generation, saved review drafts, mandatory verification and up to two
revisions. Saved drafts/reports resume across attempts. No Murtazo-owned files
changed. Unknown/limited/prohibited policy blocks before assignment generation.
Separately published Murtazo-requested SecretStr access-token and explicit API
version settings on #9 (bd944f8), default None, with six focused config tests.

Validation: 140 backend tests pass on disposable Postgres, including eight new
generation/recovery tests and six config tests. Ruff lint/format/diff pass. Scripted
models prove orchestration, not live policy interpretation or drafting quality.
No live inference/sends/production changes. Ordinary worker dispatch, automatic
policy/rubric extraction and student-facing delegation/review remain pending.
Full A3 is not complete. #12 remains open for review.

October 28 — #15 A3 worker wiring prepared on codex/drafting-worker. Migration 007
persists explicitly configured drafting requests for ready/unattempted academic
steps. The existing worker now invokes generation → saved draft → mandatory
verification → bounded revisions, with recovery from saved artifacts/reports.
Ready results complete internal tasks and queue responsibility reassessment;
policy denial/revision exhaustion blocks task/duty without consuming a worker slot.
Ordinary academic notes and chat do not automatically enable assignment drafting.

Validation: 153 backend tests pass against disposable Postgres; ten new worker
integration tests cover real run_once dispatch, private/idempotent configuration,
active-task rejection, no implicit drafting, blocked-duty fairness, retry recovery,
revision exhaustion, pause, source-version changes and unbound policy rejection.
Ruff lint/format/diff checks pass. No Murtazo-owned files changed. No live inference,
WhatsApp delivery, production migration or deployment. Student-facing delegation,
automatic policy/rubric extraction and end-to-end live usage still pending.
October 28 — #18 connection read/config dependency prepared on
codex/connection-status (based on delivery-storage #9). Adds private one-snapshot
whatsapp_connection with masked phone, nullable preferences and latest historical
delivery state. Adds optional validated public business-number Settings field,
distinct from internal phone-number ID. This supplies Murtazo's requested #17
boundary; no app/frontend files changed and no new endpoint is claimed.

Validation: 128 backend tests pass on this delivery branch, including six private
read tests and seven business-number config cases; Ruff lint/format/diff pass.
This branch intentionally excludes downstream A3 tests; the count is not a loss
of tests. No live provider calls, production migrations or deployment. Murtazo
has incorporated shared fix d61217b into #14; current GitHub checks were green.
#18 remains open awaiting interface/implementation review.

October 28 — #21 approved-template shared contract prepared on
codex/approved-templates, stacked on connection-status #19 / delivery-storage #9.
Adds scoped trusted allowlist configuration, typed text/template authorization,
parameter bounds and payload audit evidence. Old workers stay held outside the
window by default; opt-in requires typed payload support. Full reply must fit the
approved body slot; no silent notification-only replacement or truncation.

Validation: 147 backend tests pass on this delivery-only branch, including 19 new
template cases; Ruff lint/format/diff checks pass. No new migration or Murtazo-owned
implementation files changed. No real template configured/approved, provider API
lookup, live send or production changes. Template approval is operator evidence,
not inferred by code. Murtazo agreement/worker wiring and real provider validation
remain pending. Issue #21 is not marked complete.
