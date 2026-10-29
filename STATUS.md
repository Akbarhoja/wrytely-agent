# Engineering status

October 29 — #31 first drafting-authorization increment on codex/draft-requirements:
internal source-backed policy/rubric assessor implemented, 18 focused offline tests
pass; local Ruff lint/format/diff pass. Rejects stale/oversized/invalid evidence,
unbound or fabricated quotes, malformed output, missing rubric and nonpermitting
policy. Always returns authorizes_drafting=false; no task/action/storage mutation.
This is candidate semantic assessment with scripted test verdicts, not live model
quality or complete automatic drafting authorization. Concrete explicit-delegation
and atomic planner-routing contract proposed to Murtazo in coordination #4
comment6492266670; awaiting consumer agreement before dependent storage/planner
implementation. Existing analysis-only B2 contract unchanged. No app/web/source
files, migration, deployment, paid model request or message. Full exact-head CI
pending; local database fixture remains sandbox-blocked. M1 incomplete; A4 parked.

October 29 — #29 shared B2 boundaries on codex/b2-shared-boundaries: implemented
atomic create_bound_responsibility plus bounded private source/artifact/check
reads under Murtazo's recorded agreement (coordination 6491917360). Source binding
and the initial planning task commit together under the agent lock; rollback,
canonical idempotency, concurrent setup, pause/capacity and account isolation are
tested. The original setup fingerprint survives later source changes without
resetting progress. Private projections serialize UUID/time, expose stable order
and limits, retain stale status, and propagate storage failure. CONTRACTS.md
records exact shapes. No schema migration, app/web/source/transport change,
deployment or provider call. Full drafting authorization/routing remains separate;
this first path delegates analysis only. New tests were published failing before
implementation; CI run 40844538085 passes foundation and web at 4eb5c6f. A final
source-update concurrency test is pending the next exact-head CI. Local database
tests are blocked by sandbox process/shared-memory restrictions; local Ruff
lint/format/diff and the storage-failure test pass. M1 incomplete; A4 parked.

October 29 scope decision: Akbar explicitly approved M2/B2 implementation while
Meta business setup is deferred. The previous feature pause is lifted only for
the agreed B2/A3 workflow, with existing ownership unchanged. M1 remains incomplete;
A4, optional extensions, public release and additional live usage are excluded.
Codex posted a concrete proposed atomic create-and-bind boundary and private
source/artifact read projections in coordination #4, plus the required direction
for trusted responsibility-level draft intent applied before worker claim.
Await Murtazo's explicit interface agreement and exact B2 file claim before
dependent implementation. No new shared contract is agreed or implemented yet;
do not use app polling or browser-provided policy as a temporary bypass.

October 29 — #26 internal M2 validation on codex/m2-internal-validation: four new
scenario tests exercise real Store/planner/worker/drafting/verification with four
fictional observations and scripted model responses. Combined analysis → checked
revision → planner completion, private context/artifact retrieval, interrupted
review recovery without duplicate drafts, fabricated-quote rejection and the
current disclosure-body gate are covered. Full backend suite: 263 passed, two
existing warnings. No production/runtime behavior changed, paid call, real source
connection or message. This is internal evidence, not autonomous Meta quality or
live M2 acceptance. docs/M2-INTERNAL-VALIDATION.md records exact current interfaces
and remaining gaps: atomic source/delegation setup before worker claims, automatic
policy/rubric extraction and draft routing, separate-disclosure formatting versus
the current body requirement, deterministic word-count enforcement, and private
student artifact presentation. Cross-owner changes require agreement with Murtazo;
no app/web/source implementation was taken over. M1 remains incomplete; A4 parked.

October 29 independent continuation: Akbar authorized unblocked M1 checks and M2
scenario preparation while deferring Meta business setup. Restarted the existing
local production frontend; first-account saved task, answer, verified link and
preferences restored. Pause persisted across reload; Resume restored active
status. This is not the queued-work pause/restart test. All 259 backend tests pass
against disposable local Postgres (approved process access resolved the sandbox
fixture restriction), all 56 web tests and TypeScript pass, and Ruff lint/format
and diff checks pass. No new model call or outbound send. A second real participant
signed in through the separate in-app browser: authenticated responses confirm
distinct user/agent IDs, an empty private task list, no first-account phone link,
and Task not found when requesting the first account's saved task. Pausing B
does not pause A; B pause survives reload, and resume retains B's agent identity.
Both accounts were restored to active. Full two-recipient round trips and queued
work control tests remain pending. Evidence is recorded in
docs/M1-RUN-2026-10-29.md. The synthetic shared M2 scenario is prepared in
docs/stages/M2-ACADEMIC-SCENARIO.md, not executed or claimed complete. Existing
implementation ownership is unchanged; PR #25 still has no independent approval.

## Current handoff — October 29, 2026

Akbar explicitly deferred Meta legal-business setup until October 30. Resume by
checking the current account restrictions and requesting the actual operating
entity's legal name/country only when needed. Do not invent company information,
submit verification documents, or change billing while this item is deferred.
This is a saved handoff note, not a scheduled reminder.

Latest live M1 evidence supersedes the historical pending-link entries below:
real Clerk sign-in provisioned the first private agent; WhatsApp ownership linking
succeeded; the operator's synthetic M1-A question arrived and produced a saved
50-word answer through the real Meta model. The bounded reasoning run used 669
input / 1,297 output tokens. One outbound attempt was accepted by Meta, then a
signed status event reported failed with error 131031 (business account locked).
Actual WhatsApp reply delivery has NOT passed. Do not automatically resend it.

Read-only account health subsequently reported an incomplete business profile
(legal name, country, website), incomplete business verification, and a WhatsApp
payment-method issue. These are separate from Model API billing; completing one
item does not establish that all restrictions are cleared. Continuous reasoning
and delivery workers remain stopped. The temporary one-shot predeploy command
was restored to the migration command. Estimated total model spend across the
two recorded calls is $0.00773075 within the authorized $2 test budget; the
provider's monthly alert is not a hard cap.

We remain at M1 live acceptance, partially demonstrated and blocked on outbound
delivery. The continuation above records second-account task/link/control isolation;
second-recipient verification, full round trips, and queued-work live
controls/restart acceptance checks remain pending. Independent integration review
is also pending. Existing planner, memory and drafting/verification code has
offline evidence, not a completed live M2/A3 academic workflow. A4 remains parked.
Next: finish M1 acceptance, demonstrate the integrated source-backed autonomous
drafting workflow, then requirement adaptation/follow-up and multi-user evaluation.
Keep the WhatsApp-first persistent academic-agent vision and agreed ownership;
do not expand feature scope while closing M1.

October 29 WhatsApp subscription diagnosis: fresh operator linking message still
produced no inbound POST. Read-only Meta account check initially failed with
expired temporary token (OAuth 190/463); renewed the existing approved scope and
saved the refreshed token locally and in isolated Railway configuration. The
test WABA's subscribed_apps initially contained only Meta's built-in test-event
app. After Akbar's explicit approval, subscribed Wrytely Agent; Meta returned
success and a subsequent GET confirmed app 1779409246673163 is subscribed.
Operator resend is pending; linkage and real message delivery remain unverified.

October 29 Meta publishing follow-up: after Akbar's explicit approval, Meta app
Wrytely Agent was published. Dashboard showed “Your app was successfully
published”, Published status and an Unpublish control. The approved privacy notice
URL is saved. The existing student session restored; connection remains unlinked.
A fresh private ten-minute verification challenge is ready for the operator to
send. No continuous worker or additional model call was started. Actual inbound
linkage, delivery and two-account acceptance remain pending.

October 29 inbound-link blocker: operator sent a real linking message, but the
connection stayed unlinked and Railway HTTP history showed no inbound WhatsApp
POST. Meta's dashboard explicitly says real incoming events are withheld while
the app is unpublished. Akbar approved the separate pilot privacy notice;
docs/PRIVACY.md was published in e6d6e05 and verified publicly readable (HTTP 200,
no login). Its URL is saved in Meta app settings, and the Publish button is now
enabled. Publishing approval is pending; no claim of inbound delivery or M1 pass.

October 29 real browser follow-up: Chrome Google OAuth sign-in succeeded using
the existing Clerk development instance. The first account's agent provisioned
through the real web/API boundary; its empty saved-work overview and authenticated
WhatsApp controls loaded. A private expiring link challenge was generated through
the UI; operator inbound verification remains pending. All four CI checks pass on
9e86d0c. This establishes one real sign-in/provisioning path, not two-account
isolation, actual phone linkage or WhatsApp delivery. No additional model call.

October 29 M1 continuation: integrated Murtazo's published 8a407c6 loopback
origin fix and live test pack via merge 16f3232. With the actual Clerk development
configuration, the webpack production server now returns GET / and /sign-in 200,
and signed-out /api/agent/me 401. All 56 web tests, TypeScript, Prettier and the
webpack production build pass. Backend /readyz returns 200 with database,
authentication and model configuration present; live_connections_verified remains
false. No additional inference was run (recorded estimate remains $0.00138225).
Real browser login, two-account isolation, second-recipient verification and
WhatsApp round trips remain pending. Local browser access is currently disabled
in Work settings. M1 is not complete; human merge approval remains separate.

October 28 M1 live setup follow-up: dedicated Meta development key configured;
GET /models succeeded and Muse Spark 1.3 was available. One real Responses API
call through MetaModelClient completed (28 input / 317 output tokens; estimated
$0.00138225 at the published standard rates). Ignored local test-budget evidence
reserves maximum request cost before dispatch; continuous workers remain stopped.
Meta's saved $2 monthly alert is notification-only, not an enforced provider cap.
A dedicated existing-instance Clerk development key is saved in ignored frontend
configuration; a key exposed by a browser diagnostic was revoked before use and
replaced. Clerk Backend API verification and standalone SDK authentication pass.
Webpack production build passes, but configured browser routes stall before
headers while a static excluded route responds. Reproduction handed to Murtazo
in coordination issue #4; no web/auth implementation files changed. Second
consenting WhatsApp recipient verification and all live M1 acceptance cases are
still pending. These results do not establish a student WhatsApp round trip.

October 28 M1 infrastructure checkpoint: an isolated Railway development project
now hosts the integration candidate at be01bd1, with a separate Postgres
service and migrations 001–007 applied. The HTTPS API health check and WhatsApp
verification challenge passed; Meta accepted the callback and shows the `messages`
field subscribed. The existing Wrytely Clerk development instance's public JWT
verifier is configured on the backend. The latest Railway deployment succeeded;
readiness reports database and authentication configured, but no Meta model key.
This is configuration evidence, not a live student message or completed M1 round
trip. The Meta app is unpublished. The hackathon organizer's $150 Model API credit
claim was submitted with Akbar's confirmed application email and the configured
Model API Team ID after his explicit terms acceptance and submission authorization.
The form reached its confirmation page; credit allocation is not yet verified.
The Meta billing page still shows no payment method. No model calls or production
changes were made.

October 28 integration follow-up: merged Murtazo's onboarding branch through
e1a6c30 into codex/m1-integration (merge f75c0f4), including real relative link
expiry handling, malformed WhatsApp batch isolation and offline M1 regression
coverage. No merge conflicts or new feature scope; A4 remains excluded.
Local validation: 51 web tests, TypeScript, Prettier, Next production build,
Ruff lint/format and diff checks pass. Backend run passed 105 tests; 154 database
tests were blocked by macOS sandbox process/shared-memory restrictions during
disposable Postgres setup. This is an environment blocker, not a passing backend
suite. GitHub CI on the published candidate must supply combined backend evidence.
Murtazo previously reported 259 backend/51 web passing on the same executable
composition; that remains collaborator evidence, not this session's local result.
Independent review and live M1 acceptance remain pending. Meta test authorization
has progressed in the setup chat; no live provider result is claimed here.

Started October 27, 2026. Supervisor: Akbar. Lead: Codex. Engineer: Murtazo.

## Historical integration checkpoint — October 28

The snapshot below is retained as history. The October 29 entries above and the
dated M1 execution record supersede its configuration, test and live-status claims.

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
