# Engineering status

Updated November 1, 2026. [Plan revision7](docs/BUILD-PLAN.md) ·
[Work orders](docs/WORK-ORDERS.md) · [Code audit](docs/IMPLEMENTATION-AUDIT.md) ·
[Team coordination](https://github.com/Akbarhoja/wrytely-agent/issues/4)

## Product decision and actual stage

Own Wrytely runtime + Meta primary intelligence. Required first version: Canvas
extension + WhatsApp, with optional Outlook email, automatic discovery and semester supervision,
checked delegated work, revisions and follow-through. Hermes deferred. Cloud agent
must stay available while laptop is off; Canvas collection still depends on browser
and session availability. No manual-paste substitute for connector completion.

We are at **P0: live access gates open; P1 storage implementation started**, with reusable
task/draft foundations. No completed
24/7 academic agent, Canvas extension, Outlook connection or semester supervisor yet.
Historical M1/M2 live gates remain incomplete; renumbering the plan does not pass them.

Latest P0 ownership is recorded in [TEAM.md](TEAM.md): A resumes Canvas/Outlook
access completion under #104; M acknowledged and paused duplicate live runs.
[Local access check](docs/P0-LOCAL-ACCESS-2026-10-31.md): initial discovery found no company Microsoft setup; the owner subsequently
created a company-controlled directory and approved the development app registration.
Delegated User.Read/Mail.Read are configured, but publisher/actual school consent and
the actual CSU sign-in attempt is blocked by AADSTS90095/admin consent.
The local PKCE harness has 20 synthetic cases; Graph access remains untested.
Billing protection is unverified.
Outlook remains unverified but is now optional and paused by explicit supervisor decision;
it no longer gates the core product. No new/duplicate CSU approval request will be submitted.

## Current work and evidence

Supervisor execution update: Akbar explicitly removed mandatory routine agreement
and exact-file claim gates. Owners proceed with versioned interfaces and asynchronous
coordination; changes are batched into complete features. Required human merge review,
CI, correctness, privacy and live budgets remain. This overrides older “#157 awaiting
agreement” notes: A may implement private v2 result reads now. Ownership is unchanged;
M retains document journal/upload/publication HTTP and UI assembly. Next product
priority is the connected Canvas document pipeline and visible private results, then
P2 supervision—not additional standalone helpers. No application behavior changed
in this process update; stage/live completion remains unchanged.

Latest A runtime investigation on codex/p1-task-handoff-audit from #161e696be0:
100 isolated synthetic typed plan→academic handoffs passed (18.86s); original
intermittent claim failure was not reproduced and is not marked fixed. Added
fenced, content-free planner_failure diagnostics at instrumented operations,
retaining original exception/usage/retry/control semantics and no successful-path
diagnostic writes. Thirteen new cases; focused planner/worker/typed58PASS, zero
skips,9.28s. Full fresh disposable backend:1,485passed, zero skips, two existing
warnings,109.49s; all460NodePASS and Ruff lint/format234 pass. [Evidence](docs/P1-TASK-HANDOFF-AUDIT.md). No scheduling, permission, schema,
shared/public interface or M file change. #157 agreement/publication HTTP/journal
remain pending/M-owned; P0/P1 remain open. No live source/model/send/spend/grant/
install/retained migration/continuous worker/deploy/mainmerge.

Latest A cross-layer acceptance on codex/p1-document-pipeline-acceptance from
#1603ae1fc6: actual local JS producer output → real private ASGI staging API →
explicit internal Store publication → original retrieval → scoped scripted checked
v2 draft passes without fake legacy versions. Nine new focused cases pass (zero
skips, one existing warning, 2.44s), including response loss/replay, PDF gaps/partial
blocking, unchanged/changed-due events, revocation and account isolation. Full
combined first run: 1,471 passed, one existing typed-workflow claim failure;
its targeted/adjacent rerun passed34. Full fresh disposable rerun passed all1,472
tests (zero skips, two existing warnings,107.54s). Earlier cause unestablished,
recorded without workaround/skip. All 460 extension tests and Ruff lint/format232 pass.
[Evidence](docs/P1-DOCUMENT-PIPELINE-ACCEPTANCE.md).
A temporary capability probe found document publication HTTP is still missing:
existing academic/batch rejects schema2 with422/no-store, while Store publication
works. Finding6567672597 handed to M; he retains journal/upload/publication wiring.
No M module/test/fixture or application behavior changed, no duplicate journal.
#157 still awaits agreement. No live source/model/send/spend/grant/install/retained
migration/worker/deploy/mainmerge. Provider-realism review/new CI separate; P0/P1
remain open.

Latest A integration: M document-parts producer #159 exact95465a82c99e481cebd42a64f1f245152ee2b37b
merged unchanged onto #158385d5b2 on codex/p1-document-parts-integration. All five
M files byte-identical; scoped read review found no blocker. All 460 extension
Node cases and 14 actual JavaScript/Python validator cases pass (0.18s). Full
combined fresh disposable backend: 1,463 passed, zero skips, two existing warnings,
103.26s. Ruff lint/format (230 files), scoped Prettier,
byte/diff checks pass. [Review](docs/P1-DOCUMENT-PARTS-INTEGRATION.md).
Producer remains unbundled/unwired; M retains journal/upload/publication assembly.
No new source/model/send/spend/grant/install/retained migration/worker/deploy/main
merge. Counterpart implementation review/new CI remain separate.

P0 Canvas classification now has M's separate technical acceptance6565232797:
signed-in/tab/session-required, all live gaps retained. Closure record updated;
this is not unattended operation or human baseline approval. Fresh #46 remains
open/unmerged/blocked with no formal reviews; baseline approval/merge and WhatsApp
remain open. #157 private-result agreement is still pending; no dependent consumer
implementation started. P0/P1 remain open; Outlook optional/paused.

Latest A independent P1-A2 retrieval increment: bounded literal-term discovery on
codex/p1-document-term-search from #157bc717cf. Existing authorized quote pager
now supplies exact original proofs for literal terms without known capitalization,
with bounded continuation, longest/overlapping matches and final access/history
recheck. New term plus old exact-quote suites: 61 passed (27 new), zero skips, 4.45s.
Full combined fresh disposable backend: 1,449 passed, zero skips, two existing
warnings, 106.71s; all 404 extension tests pass. Ruff lint/format (227 files),
new-doc Prettier/links and diff checks pass. [Evidence](docs/P1-DOCUMENT-TERM-SEARCH.md).
Internal helper only: no model tool, HTTP/Store/DTO/schema, generator activation or
M file changes; oversized drafting-context hold remains. #157 still awaits M
consumer agreement; no dependent read implementation started. M retains #149.
No live source/model/send/spend/grant/install/retained migration/worker/deploy/main
merge. P0/P1 remain open; counterpart implementation review pending.

Latest A design slice: private v2 artifact reads proposed on
codex/p1-private-artifact-read-design from #156cba2073, responding to M's #152
consumer request. Three scoped list/detail/saved-evidence operations distinguish
saved check state from current inspection status and preserve exact mixed refs,
current source authority, source paging and pause semantics. [Proposal](docs/contracts/PRIVATE-ARTIFACT-READ-v2.md)
awaits counterpart agreement; no application behavior/route/DTO changed. Existing
v1 projections remain unchanged. Relative document links, Prettier, diff and documentation-only changed-path
checks pass; no redundant runtime suite or live source/model/send/spend/install/
deploy was run. M retains
#149 producer and HTTP/UI ownership; P0/P1 remain open.

Latest A integration: M document staging HTTP #155 exact647c5032014af444eea114992773cbb3b438bb1c
merged unchanged onto #153f62fb0c on codex/p1-document-api-integration. All5 M files,
including app/main.py, byte-identical; read review found no blocking issue in scope.
POST begin/parts/finish reuse current Store and retain default-off trusted extractor
configuration and bounded/no-store/error/replay semantics. On fresh disposable
Postgres, all 54 focused API tests pass (zero skips, one existing warning, 6.83s);
full combined backend passes 1,422 tests (zero skips, two existing warnings,
137.85s). All 404 extension tests pass;
Ruff lint/format (222 files), scoped Prettier and diff checks pass. [Review evidence](docs/P1-DOCUMENT-API-INTEGRATION.md).
M's #153 counterpart integration/CI review6564595290 found no blocker;404NodePASS,
existing dependency GitHub CI green. M's #152 scoped consumer review passed16pure
cases, requesting a separate versioned private result interface; no public v2
exposure. M has resumed #149 producer, not delivered yet. Counterpart review and
new candidate CI remain separate. No live source/model/send/spend/grant/install,
retained migration, worker/deploy/mainmerge. P0/P1 stay open.

Latest A integration increment: M's browser controls/package #146 exact
c9deb62434365ce7af22fbc7772f5fafc11cdfcc merged unchanged onto #1524dd8a06 on
codex/p1-browser-package-integration. All16 delivered files byte-identical; A read
review has no blocking finding in scope. Exact M archive and combined candidate
404NodePASS/zero skips; synthetic-only ignored package builds with complete local
module closure and fixed example.edu origins; default-disabled worker test makes
zero requests/alarms. Full combined disposable backend1368PASS/zero skips/
2existingwarnings99.14s. Ruff/format
217files, delivered UI/doc Prettier and diff checks PASS. A-owned CI command now
includes host/UI/package tests previously omitted by its static list; candidate CI
evidence remains separate.
[Review evidence](docs/P1-BROWSER-PACKAGE-INTEGRATION.md). No independent A rendering,
installed Chrome/source/session/CSP proof, real pairing, model/send/spend, grant,
retained migration, worker activation, deployment or mainmerge. Counterpart review
pending; M retains extension/app/web ownership. P0/P1 remain open.

Latest A internal P1-A2 increment: typed document drafting on
codex/p1-typed-document-drafting, base #1510345cc8. Existing requirement assessment,
policy preflight, generation, format/semantic verification, saved artifacts, bounded
revision and recovery now accept exact legacy/document evidence for policy/rubric/
claims. Actual synthetic document-only publication reaches internally checked draft
with zero legacy versions; mixed real inline/document refs also pass. Original text
and structured rubric fields are read through the leased object scope. Migration022
versions internal artifacts; old website projections hide v2 rows pending M consumer
agreement. Earlier document_drafting_not_wired hold is superseded by this path.
41new type/workflow cases PASS; full combined disposable backend1368PASS/zero
skips/2existingwarnings99.23s; extension389NodePASS; Ruff/format213files/diffPASS.
Counterpart review pending. No live Meta call/schema/quality proof, Canvas
collection, WhatsApp send, worker activation, retained migration or deployment.
Complete context over80000 code points/512000 serialized bytes explicitly requires
further paged investigation rather than truncating or certifying missing policy.
Counterpart review and versioned HTTP/UI assembly remain separate; P0/P1 stay open.

Historical slice notes below preserve the evidence and limits at their original heads.

Current integration candidate: codex/p1-host-integration from #150493a5cd plus
M #144945d1c5 merged unchanged (six files checked byte-for-byte). A reviewed both
host modules and independently passed24focused/all389Node on the exact M archive;
combined candidate389NodePASS. Controller remains inactive until explicitly enabled;
no real alarms, extension installation or source calls were performed. Full combined
backend1327PASS/zero skips/2existingwarnings88.44s; Ruff/format208files/diff PASS.
Counterpart integration review pending. #146 package is included in the newer candidate above; installed-browser proof
remains separate. This host-only candidate did not include the package.

Latest A P1-A2 increment: explicit Canvas object task scope on
codex/p1-canvas-object-scope, stacked on #143. M's #142 design agreement6560955094
received. Atomic scoped delegation, exact/current-authorized replay and existing
leased object reads work with actual document-only publication and zero fake legacy
versions. Control/content changes fence old work; unchanged sync preserves task and
revision while old pinned observations remain historical. New document intents are
explicitly held without inference until typed v2 generation is wired.39new scope
cases PASS; prior focused140PASS plus final new-generation case. Full disposable
backend1327PASS/zero skips/2existingwarnings88.71s; Ruff/format206files/diff PASS.
Counterpart review pending.
Migration021 test-only; no app/HTTP/extension/source/model/deploy activation.

M update: #144 host and #146 UI/package delivered, both author CI SUCCESS; A exact
host read review and24focused/all389Node tests PASS on exact945d1c5; host
integration passed the combined checks recorded above; #146 package review/integration
is recorded in the newer candidate above. M independently
reviewed #129/#131/#133/#135/#142/#143 as scoped evidence, not the entire stack.
M's #148 document HTTP design now explicitly agreed by A6563512653, with first
implementation base #135019d6c7; M retains app/producer/UI ownership. P0 baseline
human review/WhatsApp and full P1 live collection remain open; Outlook optional.

Latest A independent P1-A2 slice: bounded original-section quote discovery on
codex/p1-document-quote-search, stacked on #142. Internal search produces exact
citation proofs from existing scoped readers, preserving Unicode/PDF provenance and
repeated/overlapping matches with explicit continuation. Postflight reads recheck
current access/coverage; no-match results cannot prove absence of course policy.
Focused disposable-Postgres74PASS (34 new search cases); full disposable backend
1288PASS/zero skips/2existingwarnings100.66s. Ruff lint/format204files and diff checks
pass; counterpart review pending.
No Store/HTTP/model DTO, task capability, source activation, migration, generator
wiring, provider call or M-owned file changed. Document-only drafting proposal still
awaits M agreement. P0/P1 remain open; workers stay stopped.

Latest A follow-up: P1-A2 document-source recovery on
codex/p1-document-draft-recovery, stacked on #141. Unavailable/stale document evidence
now stops the generator instead of spending further prose-revision calls. A proposed
[document-only scope/drafting boundary](docs/contracts/DOCUMENT-DRAFT-SCOPE-v1.md)
awaits M agreement before task-capability/typed-consumer implementation. No generator
reference production, document-only activation, HTTP/extension change or deployment
is claimed. Focused disposable-Postgres38PASS (8 new recovery tests); full disposable backend1254PASS/zero skips/2existingwarnings82.48s. Ruff
lint/format202files and diff checks pass. Counterpart review pending; P0/P1 remain open.

Latest A increment: **P1-A2 pinned-document draft verification** on
codex/p1-draft-document-verification, stacked on #140. Internal immutable
provenance now feeds exact original-section checks before model review and is
revalidated at successful commit, cached recovery and private-completion gates.
Canvas checks use draft-purpose6h, not inspection24h. Focused disposable-Postgres
suite **118 passed** (22 new provenance cases); full disposable backend **1246 passed**, zero skips, two existing warnings
in80.23s. Ruff lint/format200files and diff checks pass; counterpart review pending.
The existing migration-repeat test now includes020. Positive bridge fixtures use
the actual staged version with a test-only legacy pointer; no product activation
is implied. Same text from another source cannot impersonate the cited document.
Migration020 is disposable-test-only. No HTTP/model DTO or M-owned file changed.
Current generator does not yet provide pinned references: document-only task scope,
generation consumers and live collection remain unfinished. No P0 closure, live
provider call, production migration, deployment or continuous-worker activation.

| Step/component           | Owner             | State and evidence                                                                         | Next action/blocker                                                                         |
| ------------------------ | ----------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| Revision7 planning / #44 | A                 | Code/PR audit and ordered work orders prepared; docs only                                  | Counterpart review; new interfaces still proposals                                          |
| P0-A1 baseline           | A                 | codex/p0-baseline combines #40/#42, revision7 and M Canvas proposal; main not consolidated | CI391/114 plus M independent local391/114 pass; human approval still needed                 |
| Diagnostics #40          | A                 | ddd5ab1, scoped counterpart review;381 backend/113 web CI reported                         | Included in #46; not deployed                                                               |
| Pause recovery #42       | A                 | 224bc96 (code a7db006), scoped review;385 backend/113 web CI reported                      | Included in #46; combined CI391/114 passed, review pending                                  |
| Murtazo #28              | M                 | a344642 UI; latest a383782 Canvas proposal;114 local web reported                          | Reuse proposal findings; extension supersedes initial OAuth path                            |
| P0-A2 Meta               | A                 | P0 real tool/saved-result/continuation proof passed in #50; academic M2 remains open       | Two-call probe passed (see #50); failed-call reservation retained                           |
| P0-M1 Canvas             | A (reassigned)    | M #64 lifecycle API reviewed/21 cases pass; local diagnostic work reported                 | v5 known PDF read/matched; rubric, remaining session matrix and review pending        |
| P0-M2 Outlook            | A (reassigned)    | M #54 at4aadc91 offline Graph probe;32 cases independently pass                            | Optional/paused: CSU admin consent required; not a core stage blocker                       |
| P0-M3 WhatsApp           | M                 | Linking/inbound worked; last delivery failed131031                                         | Business/account resolution and delivered-reply proof                                       |
| P0-A3 interfaces         | A                 | C1/C2, C3 short-text and exact #118/#119 document/C4–C7 DESIGN agreed by M                  | Implementation and counterpart acceptance remain; no activation from design agreement       |
| P1 collection/memory     | A/M by work order | P1-A1 #58 adds staged academic text/check/event transactions; collectors not assembled     | 633 A backend pass; M transport/journal separately reviewed; live assembly/segments pending |
| P2 always-on ownership   | A/M by work order | Existing task worker; continuous workers stopped                                           | Supervisor, schedule, hard budgets and bounded deployment                                   |
| P3/P4 work/adaptation    | A/M by work order | Private drafting/checks scripted; live artifact not produced; A4 parked                    | Real accepted work/delivery, revisions and follow-through                                   |
| P5/P6 pilot/release      | A/M by work order | Not started                                                                                | Reliability, live evidence and release approval                                             |

P1-A1 first slice: full disposable-local-Postgres suite **459 passed**, including38
connection-lifecycle cases and30 digest cases; Ruff lint/format and doc/diff checks pass.
Migration010 was applied only to disposable tests, not Railway. No route or collector wired.
Requested operator config #61 adds25 tests; combined local backend **484 passed**.
M #60 assignment mapping independently reviewed/tested:32 mapper +28 digest cases pass
oncc5d793 in an ignored archive; no actual source/provider access proved.

Discovery/context/scope/list slice adds36 tests; full fresh disposable backend **520 passed**.
Migration011 and lifecycle reset hooks were tested only locally; no API or provider collector
was added to this branch. Catalog pages and receipts are atomic; academic source versions,
checks/events/segments and Outlook credentials remain unfinished. M #64 exact57ca6ea
received independent read-only review with21 API tests passing in an isolated archive.
Its implementation is on M's branch, not included in the520 backend count.

Academic-content increment adds28 tests; full fresh disposable backend **548 passed**.
Assignment, syllabus, page, announcement, discussion/entry, submission and grade text/fields
are staged atomically with checks/events/checkpoints and receipts. Immutable source storage
is reused; no legacy latest source pointer/model activation. Migration012 was test-only.
No extraction/provider collection, document segments, new API or live worker is claimed.

Internal P1-A2 freshness increment #73 adds37 tests; full disposable backend
**585 passed**. Legacy timestamp checks share one policy; final ready commit, cached
successful report recovery and private-draft completion recheck current owned evidence.
Staged Canvas policy boundaries are tested but unwired. C3 retrieval and document
segments remain pending agreement; P1-A2 is not complete. No deployment, migration,
paid call, source activation or continuous worker change occurred.

A counterpart reviews: M #66 exactbdb0e89 HTML extraction independently passes45
focused cases plus2,744 small malformed-input probes and six targeted samples;
M #70 exactb09535f pairing client independently passes53 Node cases. No scoped
blocking finding; these are isolated helper/module tests, not live collection,
installed MV3 storage/restart evidence or combined API/client acceptance.

M #68 exact36215bc web lifecycle proxy received A counterpart review: full151 web
tests (37 new) and TypeScript checks independently pass in an ignored exact-head
archive with matching lock dependencies. No scoped blocking finding. This is proxy
component evidence, not real Clerk/Canvas access or combined deployed acceptance.
No M-owned files, credentials, provider configuration or deployed behavior changed.

Shared PDF packaging #75 provides pypdf6.21.4 for M's requested future extractor; exact
version and hashes are in uv.lock. Locked install, trusted synthetic text-PDF smoke,
unchanged existing-version audit and full585 backend tests pass. The proposed subprocess/memory/CPU/wall
boundary is in docs/contracts/PDF-EXTRACTION-BOUNDARY.md and awaits M agreement.
No PDF extractor or document-segment/reader activation is included.

P1-A2 #77 adds a detailed proposed C3/long-document contract for counterpart review:
scoped paged reads, original sections, immutable manifests and fenced staged document
publication. Documentation only; no reader, upload, schema2 batch or source activation
implemented. Fresh #4/comments/formal-review check found no new M reply on
#71/#72/#74/#76; agreement remains the dependent implementation gate.

Current reviewed/corrected checkpoints (separate branch evidence): M accepted #84
ordering/canonicalization fix581a9f5 after independent597 tests and original repro.
Reader #86 c464ecd had623 passing tests but a newly reproduced NFC-expansion paging
defect; #97 fixes canonical size on every staged path and legacy continuation without
truncation. Current A full backend **633 passed** (10 new cases, six initially RED).
M independently accepted #98 exact59c074e focused Unicode cases; the reader remains unwired and undeployed.

M #94 exact8bc90b0 discovery HTTP received A review and independently **68 API cases
passed**. M #96 exact95c38cb journal received A review and independently **119 Node
cases passed**. These do not establish actual extension/server compatibility or live
Chrome collection. M is approved as single editor for the proposed cross-layer
HTTP interoperability test/harness after a scoped claim. Conservative54001 retained
resource rows/8MiB journal-finish reply accepted as a bound, not a proved6000-course run.
CI coverage for the journal is a separate A-owned follow-up; no missing-file skips.

P0 core checkpoint: Meta access proof passed. A owns Canvas feasibility; the operator supplied a new current-session report after local installation:
7 courses discovered/1 selected; 22 assignments/12 instruction bodies; inline syllabus
and one discussion view readable. No positive rubric proof. One syllabus PDF manually downloaded and locally text-readable;
extension document reading remains unverified.
A second operator report returned the same reads after closing Canvas tabs with Chrome
and the worker Console open. Manual tab-closed access is supported by that report;
after operator-performed Chrome restart, diagnostic reported login_required and A
observed the official NetID login form. Post-login dashboard and operator-reported sampled extension reads recovered; unattended worker,
explicit Canvas sign-out also returned login_required in the operator probe. Natural
timed expiry and account-switch checks remain untested. Browser controls
cannot open extension management. No restart/logout was
performed. Outlook is optional/paused and not a core blocker. M retains WhatsApp delivery.
Baseline #46 exact9bbea97 still has no formal review and is merge-blocked; a human review
was formally requested from murtazokhon-tech. C4–C7 and the exact document-wire decisions
await counterpart agreement; no protection/interface gate was bypassed.

A independently checked M #107 exact4106dc88 in an ignored archive: **233 Node tests
passed, zero skips** across all six requested suites. Read collector, client injection
and discovery lock/journal changes; scoped review posted on #107. This is course metadata
only, with academic resources honestly open; not installed/live Canvas or collector-driven
HTTP/Store proof. M owns active #108 for that next cross-layer acceptance scenario.

Other counts above belong to their cited commits and historical runs. Current source/status two-account live denial
checks passed previously; live artifact isolation remains untested because no live
artifact exists. Read the [actual M2 run](docs/M2-RUN-2026-10-29.md).

## Operating limits retained

Last verified deployment: isolated Railway API, code1dcb4d3; migrations001–007 +009,
not008. No continuous reasoning/delivery worker enabled. No production release.

Known Meta usage after the approved two-call diagnostic is$0.01114350 plus unchanged
unknown-use reservation$1.32 = $1.33114350 charged/reserved against$2. Probe cost
$0.00341275; both diagnostic calls consumed. [Report PR #50](https://github.com/Akbarhoja/wrytely-agent/pull/50)
records the evidence; no additional call implied. Browser access restored, but rounded
aggregate usage did not reconcile the failed request. Available$150 credits do not
increase spending authorization. Original M2 scope remains one synthetic workflow,
<=10 requests/<= $1.50 within$2, no WhatsApp sends, continuous workers stopped.

P0 Canvas document access: the operator's v5 live report reads the known syllabus
PDF (**398346 bytes**, one manually validated redirect, PDF signature true, private
SHA256 matches the separately saved/local-parsed sample). Both existing file and CDN
host grants report true. Seven courses discovered; two selected courses have22/23
assignments and12/9 instruction bodies. Four assignment detail samples read but no
rubric criteria were observed. One discussion topic view read; whole discussion
coverage remains partial. This passes the bounded PDF retrieval check, not the whole
P0/collector gate. Live account-switch/natural session-expiry and unattended worker
recovery evidence remain unproved; M reviewed the scoped implementation and found a Windows test-path defect; A fixed
it with fileURLToPath and refreshed the PR description; Windows re-review pending.
64 synthetic Node tests
and685 disposable backend tests passed on100d5a2 before the operator run. No P1
collector/scheduler/runtime behavior changed; see the dated access record for history.

Latest M handoff: #116 at36c1740 reports17 actual assignment HTTP/Store scenarios
and721 backend/310 extension tests; A has read the handoff, not independently
validated those results. M now claims assignment collection; no takeover. A's
Canvas rubric UI attempt initially hit an origin-approval block; supervisor approved
inspection and normal CSU NetID navigation recovered Canvas through existing SSO.
Two additional selected-course assignment pages showed no visible rubric. A known
positive rubric sample is unavailable: supervisor knows of none. Keep capability
unverified; no more blind reruns or false denial/pass.
The dated access record now consolidates the session/content evidence matrix.

P0-A3 follow-up: proposed exact document-only schema2 wire now specifies staged
upload and publication/receipt shapes, structured-field binding, canonical synthetic
vectors and bounded orphan cleanup. M agreement is required before consumers;
schema1 and production code are unchanged. Ten synthetic vectors independently
match Python and Node canonical hashes/offsets;30 existing digest tests pass,
proposal/fixture formatting and links/diff clean. This addresses M's explicit #78 request,
not an implemented document upload or completed P0 gate.

P0-A3 C4–C7 now has an exact operations review candidate with20 synthetic cases,
including one-use dispatch, offer-bound decisions, checked-file streams, conservative
budget settlement and activation/rollback defaults. Agreement/implementation pending;
existing consumers and paid authorizations unchanged.

A counterpart review of M #116 exact36c1740:310 extension Node tests pass. The17
actual loopback/API/Store cases all stop at configuration before client setup on this
Mac because Node adds __CF_USER_TEXT_ENCODING and the driver rejects its name.
A isolated the first failure and reproduced the runtime-added name with only the
parent-whitelisted environment; reported #116/6553629521. M retains the harness fix;
no files changed/bypass performed and HTTP acceptance is not independently certified.
M's earlier721 backend result remains separate implementer evidence.

P1-A2 structured change details implemented: private existing events now identify
changed canonical field names and title/content/coverage/missing flags, linked to the
latest prior observation of the SAME owned object. Additive014 keeps old rows null,
existing kinds/C2 receipts unchanged; no text/rubric values are copied into events.
Twelve new transactional cases cover initial/combined changes, replay, Unicode/date
canonical equivalence, A→A→B→A, failed-batch rollback, cross-object FK denial and
legacy inserts. Seven first failed for absent columns. Final full disposable backend
**697 passed**, two existing warnings; Ruff lint/format and diff checks pass. The first
full run identified only the store test's expected ledger ending at013; A updated its
explicit expected list to014 without weakening repeat-migration safety.014 applied
only to disposable tests; no API, source/model activation, send or deployment.

P1-A2 internal document sections implemented on codex/p1-document-sections from
A#12042cb2f7, NOT the known-failing #121 candidate. Pure whole-text normalization,
immutable bounded sections, exact manifest/part validation, code-point offsets,
UTF-8 hashes and bounded original-section paging follow M's accepted architecture.
PDF page gaps remain explicit; no parser, root hash/wire, storage/API or source/model
consumer added.53 new focused cases pass; standalone full disposable backend750PASS,
2existingwarnings in29.64s; Ruff lint/format127files and diff checks pass. Existing
#121804PASS/10FAIL Mac-harness evidence remains separate and unresolved. M's collector,
parser, harness and all files unchanged. #118 agreement still gates upload consumers.

P1-A2 internal document storage on codex/p1-document-storage: additive015 stores
owned immutable section versions/segment IDs and exact observation bindings. Trusted
transaction-only staging/binding helpers and pinned verified-user/task reads reuse
current scope/generation/subject/expiry/freshness/lease fences. Unbound/partial writes
are unreadable; failures roll back all parts/bindings; same-body A→B→A reuses immutable
sections with distinct checks. Internal section fingerprints are not protocol digests.
29 new DB tests (first25 focused pass) and full standalone disposable backend779PASS,
2existingwarnings in36.60s; Ruff lint/format129files/diff clean. Includes cross-account/
object/root/observation denial, corruption, concurrent dedup, rollback, stale/failed
checks and lease expiry during read. No #118 upload wire, API, parser, source/model
promotion, cleanup worker or retained migration. Existing #121 failures remain separate.

Latest M resumed/review update: #109baf565e independently64/64 Windows Node pass,
portability fix cleared; #122b01c3ab independently53 pure-section tests pass, scoped
no blocker. #12042cb2f7 static review has no blocker, DB execution remains M-untested.
#118605e501's10 vectors independently pass M's actual JS helper, but exact staging
versus publication discriminator wording needs clarification before final agreement.
#11978a3fb7 retains prior behavioral agreement; atomic dispatch consumption, consumed
offer/different-key decisions and typed health projections need exact wire clarifications.
M is prioritizing the owned macOS harness fix and preserving his collector worktree.
New storage #124ee41cb0 is separately awaiting counterpart review; no blanket approval.

P0-A3 requested clarifications are now addressed in original PR revisions:
#1187f4f09f scopes publication schema2/batch_type separately from staged schema2/operation
and adds8 shape examples while preserving all10 digest vectors. #1193b86710 specifies
commit-before-permitted dispatch consumption, accept-only responsibility creation,
consumed-token/different-key409 with no side effects, and exact typed operator/worker/
student health projections. Original20 review examples unchanged;4 edge cases plus2
health samples added. Shapes/arithmetic/privacy-key/link/format/diff checks pass.
These docs/fixture updates are carried into this storage branch; runtime remains
ee41cb0 with779 full tests previously passed, no redundant runtime rerun. Final M exact
agreement is requested; no consumer, permission, paid allowance or deployment activation.
M's #125 harness fix and #126 collector handoffs have arrived for separate A review.

Historical #121 candidate evidence (superseded only by a separately recorded rerun):

P1 integration candidate: A42cb2f7 combined with M#11447d076d on isolated
codex/p1-integration-candidate, preserving A shared/contracts and M app/extension
byte-for-byte. Academic+connection API components independently74PASS; all8 extension
suites310PASS. CI foundation now pins Node24 and extension CI covers all8 files.
Combined full disposable backend804PASS/10FAIL (2existingwarnings): the10 inherited
actual-client cases all fail at the known Mac environment guard before setup; no
skip/bypass. Separate diagnostic64PASS, web114PASS and TypeScript, Ruff/format/CI
format/diff pass. Source collector handoff and M harness fix are still required.
No deployed/live collection or main merge; see [candidate evidence](docs/P1-INTEGRATION-CANDIDATE.md).

November1 combined candidate `codex/p1-collection-integration`: A#124bba479d plus
M#12545dbebf and #126e7558f7, with prior #121 CI/evidence retained. Actual macOS
17-case client/HTTP/Store suite now passes on exact #125; its21 environment-policy
cases also pass without bypass. Exact #126 extraction API/parser59 and focused
reader/discovery/course143 Node cases pass. Combined extension365/zero skips,
separate diagnostic64, web114 and TypeScript pass. CI pins Node24 and enumerates all10
extension test files. M source preserved exactly except the separate exact #125
harness files and retained A-branch Outlook probe; shared014/015 retained.

First combined backend run:961PASS/1FAIL in56.00s. Existing source ambiguity test
exposed cross-zone datetime equality during today's DST repeated hour. Both fixed
2025 Denver fold reproductions failed before the fix. A-owned ec6f0c9 compares UTC
instants; regressions cover rejection/rollback and chronological promotion despite
reversed wall clocks. Final combined backend **964PASS**, zero skips,2 existing
warnings in51.53s. Ruff lint/format173files, CI format and diff checks pass.
See [combined evidence](docs/P1-COLLECTION-INTEGRATION.md). Counterpart review of this
candidate/DST fix/#124 remains pending; final #118/#119 agreement was subsequently received. Full actual
collector→extractorHTTP→Store two-course initial/repeat/changed-deadline acceptance
is M's next sole-editor harness slice, not passed by these component scenarios.
P0/P1 remain open; no live Canvas/model/WhatsApp, retained migration, install,
continuous-worker activation, deployment or protected-main merge occurred.

## Next actions

A: obtain counterpart review of the combined collection/storage candidate, its narrow
DST fix and #124 storage; obtain human baseline approval. Exact #118/#119 DESIGN
agreement is recorded below; continue owned staged-document work in reviewed slices.
M: next sole-editor harness slice proves actual collector → extraction API → Store
for synthetic two-course initial/repeat/changed-deadline flows; then remaining Canvas
resource kinds/documents and installed-host recovery. WhatsApp live delivery remains M-owned.
Claims must be posted in #4 before implementation. Nobody takes over the other's files.

[Historical detailed status](docs/archive/STATUS-through-2026-10-29.md) preserves
prior runs, authorizations and limitations. Old stage documents are context; this
revision's scope and work orders determine new implementation.

P0-A3 #118 exact-key clarification: publication uses schema_version2 plus
batch_type=canvas_documents; staging uses schema_version2 plus its exact operation
and forbids batch_type. Endpoint-specific dispatch never guesses from version alone.
Eight synthetic wire examples supplement the unchanged ten canonical vectors. M final
review requested; no executable upload or agreement/activation inferred.

P0-A3 #119 clarification: authorize_agent_dispatch itself commits one-use consumption
and dispatch_at BEFORE returning permitted; no separate M consume operation. Only
successful acceptance creates a responsibility; consumed-token/different-key reuse
returns409/offer_consumed without new authority or side effects. Operator, heartbeat
and student health DTOs now have exact fields/types/nullability and separate scope.
Four examples plus two health DTO examples supplement the unchanged20 prior cases.
This branch includes #118's7f4f09f staging/publication clarification. Final M agreement
is requested; no consumer implementation, budget or activation change.

November1 design gate update: M agreed #118 exact7f4f09f in6554751370 and #119
exact3b86710 in6554751518. Exact design ambiguities are resolved; prior pending
statements above are historical. No upload/action implementation or activation is
implied. #128 exact1cbb61d CI41283546158 completed SUCCESS (all4 jobs), separate from
its local964 backend/365 extension evidence. M owns active two-course HTTP claim
6554737880; A does not edit those harness files.

P1-A2 document-root validation on `codex/p1-document-root-validation`, executable
5d46e73 from #1281cbb61d: agreed #118 exact header/resource/owner/field bounds,
configured extractor, immutable sections and canonical v1 root/digest implemented
in a pure helper. Reuses section and schema1 academic-field validators; file fields
are explicit. Complete/empty/page-gap checks preserve honest coverage; course and
provider identity remain outside content hash. Ten unchanged root vectors match
exact bytes/SHA256;98 new tests pass, including200000-character text and deadline/
rubric changes. Focused section+root151PASS; full disposable backend1062PASS,
zero skips,2 existing warnings in51.37s; Ruff lint/format176files and diff pass.
No staged request parser/store, SQL, upload/publication, M source/harness, live source,
model, send, worker or deployment change. Counterpart review requested.
M reports #127 two-course actual tests green, final782 full suite still running;
this is implementer progress, not A review/combined/live acceptance.

P1-A2 DST audit follow-up on `codex/p1-freshness-utc`, base#129d70c9a8:
M's #130 duplicate source-time blocker already fixed by Aec6f0c9; exact commit
handed off in6554869602 and M acknowledged6554875745. Further audit reproduced
nine freshness failures (local elapsed TTL/future/min/max/urgent limits) and two
Canvas same-instant ambiguity failures in fixed Denver fold tests. f5a2f34 normalizes
policy clock/evidence to UTC; c29aba6 normalizes Canvas current/prior instants.
Preserves age thresholds, all permission/coverage fences and historical semantics.
13new policy +2 transactional regressions; final full disposable backend1077PASS,
zero skips,2existingwarnings52.92s; Ruff lint/format177files/diff pass. Tests also
cover spring-forward, exact limits, rollback and reversed wall-clock history/order.
[Evidence](docs/P1-FRESHNESS-UTC.md). No M-source/HTTP/schema changes, live access,
spend/send, retained migration, worker, deployment or main merge. Counterpart review
requested; document staged transactions/publication remain next A implementation.

P1-A1/A2 private document staging on `codex/p1-document-upload-staging`, executable
a0b0ac9 from#1314b52c6a: begin_document_upload/put_document_parts implement agreed
#118 begin/put only. Additive016 stores private headers/parts/original receipts,
scoped by connection/generation/scan composite FK. Existing actor/agent/connection/
scan locks fence current identity/scope/lease/expiry before replay and final receipt.
Exact staging keys/discriminator/1MiB request bounds; immutable declared hashed
parts, fixed <=30min expiry,4unexpired uploads and8MiB retained UTF8 text quota.
Expired uncollected text remains counted; no cleanup/publish/ready-root exists yet.
44 new transactional cases pass; final full disposable backend1121PASS/zero skips/
2existingwarnings60.42s; root+section151PASS, Ruff/format/diff/link checks pass.016
applied only to disposable tests. No observations/legacy versions/source readiness
are produced. [Evidence](docs/P1-DOCUMENT-UPLOAD-STAGING.md). Counterpart review requested.

M reviews now received: #1246554904893 storage/no scoped blocker/96 focused DBPASS;
#1286554904699 combined+UTC/no blocker/96DB+365NodePASS. #1296554905045 helper
151purePASS under UTF8 mode, but native Windows fixture default decode failed. A
fixed original #129 test read explicitlyUTF8 in82697f5, then merged into staging
5daffed;151 focused tests pass after merge. Native-default Windows rerun remains M
evidence, not inferred here. Runtime staging code unchanged from1121-pass a0b0ac9.
M#13200dad2ac two-course handoff received (966Windows backend reported); A exact
Mac counterpart/combined verification is next separate review, not yet passed.
No M files/fixture bytes modified; no live source/model/send/spend/grant/install/
retained migration/continuous worker/deploy/mainmerge. Finish/root publication and
safe cleanup remain subsequent A slices; P0/P1 stay open.

P1 two-course acceptance: exact M#13200dad2ac merged unchanged into
`codex/p1-two-course-acceptance`, executable015dde1/base#133c107b68. Four M
test/scoped-doc files verified byte-identical; A shared/runtime/contracts preserved.
Independent Mac all19 actualHTTP/client/extractionAPI/Store PASS8.38s;365NodePASS.
Full combined disposable backend1123PASS/zero skips/2existingwarnings61.80s;
Ruff/format183files/diff pass. Synthetic committed two-course initial/repeat/deadline
change proves2→2→3 versions/events,2→4→6observations and exact lost-ack replay without
refetch. No scoped blocker; [review](docs/P1-TWO-COURSE-ACCEPTANCE.md). Not installed
MV3/restart/live/all-source/modelactivation acceptance. A document finish/publication
continues separately; no M implementation edit, live/send/spend/retainedmigration/
worker/deploy/mainmerge. P0/P1 remain open.

P1 finish transaction implemented on `codex/p1-document-finish`, executable340b599
from#13481f000a. Existing immutable staged parts reassemble through agreed full-root
validation;015 sections reused with017 protocol identity, preserving old internal
fingerprints and distinguishing changed dates/rubrics. Same-object A→B→A deduplicates
ready roots; no observation/source/checkpoint/event is published. Final current
authority/expiry fence rolls back shell/root on failure.13new cases,86focused
upload+storagePASS; full disposable backend1136PASS/zero skips/2existingwarnings
63.36s; Ruff/format184files/diff pass.017 is test-only; counterpart review requested.
Zero-text gaps, cross-section NFC, missing parts, scope/revocation/expiry, parallel
finish, changed fields and atomic rollback checked. Publication follows separately;
no M API/collector edit, live/send/spend/retainedmigration/worker/deploy/mainmerge.

P1 document-only publication implemented on `codex/p1-document-publication`,
executable7339a59/base#135019d6c7. Exact schema2/batch_type parser uses existing
commit_sync_batch namespace and scan/lease/credential/scope/checkpoint fences. Ready
owned roots atomically produce observations,015 section bindings, original-field
change events, resource items/checks, checkpoints and receipts.018 records resource
inline/document mode and published uploads; schema1 remains unchanged, mixed modes
reject. No legacy empty text versions or source/model activation. Metadata exposes
pinned root IDs; protocol documents cannot masquerade as short empty source bodies.
27newcasesPASS; full combined disposable backend1163PASS/zero skips/2existingwarnings
68.49s. Ruff/format188files/diff pass. Repeat/changed-deadline/reversion,100000-emoji
paging, partial/failed latest evidence, file scope, historical/ambiguous captures,
all-or-nothing batch/lease rollback, cross-account denial and shared replay namespace
verified. [Evidence](docs/P1-DOCUMENT-PUBLICATION.md).017/018 test-only; independent
review and M consumer/installed/live assembly remain required; safe cleanup pending.
No M API/collector edit, live/model/send/spend/grant/install/retainedmigration/worker/
deploy/mainmerge. #134/#135 counterpart review requests remain distinct.

P1 safe staging cleanup implemented on `codex/p1-document-cleanup`, executable
8f8d1e3/base#137afc42c9. Explicit operator-only method selects<=100 expired uploads
and<=100 old orphan protocol roots, agent-before-row SKIP LOCKED with reference/
expiry rechecks and atomic rollback. Scrubs headers/parts/ready pointers, retains
content-free upload tombstones and exact original receipts. All bindings/history/
matching observation payloads and retained upload pointers protect roots; root age
>=24h, legacy internal roots excluded. No source/event/freshness mutation.
21focusedPASS; full combined disposable backend1184PASS/zero skips/2existingwarnings
69.82s. Ruff/format191files/diff/link checks pass.019 applied only to disposable
tests; no maintenance was run on retained data. [Evidence](docs/P1-DOCUMENT-CLEANUP.md).
Previous #137 exactafc42c9 CI41288720692/41288717315 SUCCESS; new cleanup CI separate.
Counterpart reviews/consumer assembly remain pending. M retains host/HTTP/extractor/
extension work; no M file edit/live/model/send/spend/grant/install/retainedmigration/
worker/deploy/mainmerge. P0/P1 remain open.

## Current non-WhatsApp P0 closure audit — November1

Supervisor explicitly prioritized finishing P0 excluding WhatsApp.
[Consolidated closure record](docs/P0-CLOSURE-2026-11-01.md) separates feasibility
classifications/design agreement from P1 implementation and live activation. Meta
#50 real tool→saved-result→continuation proof is passed; its original report is now
restored byte-identically froma7bc400. Exact C1/C2, C3 architecture/#118 and C4–C7
#119 design agreements are recorded. Outlook remains optional/paused, not a core gate.

Canvas evidence is gathered: signed-in sampled text/PDF reads and negative-login/
recovery classifications exist; rubric/live-account-switch/natural-timeout evidence
remains explicitly unknown. Current read-only dashboard reload still shows7 courses.
Proposed conservative tab/session-required feasibility classification is submitted
for M counterpart acceptance, NOT a claim those unknown checks passed or that
unattended collection works. P0 work-order outcome is reviewed classification and
gaps; P1/P2/P5 recovery/full-collection requirements remain unchanged.

Baseline#46 exact9bbea97 remains green/technically reviewed391backend114web and
ancestry checked. Formal human reviews are still empty; main requires1approval.
AuthorAkbarhoja cannot approve its ownPR; another account alone is not independent
human review under TEAM.md. Murtazo's review is requested. Non-WhatsApp P0 cannot
be marked closed until this normal approval/merge and Canvas decision are recorded.
WhatsApp remains excluded/M-owned, not passed. No P1 code/permission/budget/live
source/model/send/grant/install/restart/logout/retainedmigration/worker/deploy/main
merge changed in this audit. Links/provenance/arithmetic/diff checks passed; unchanged
application suite was not redundantly rerun.

P1-A2 original-section citation helper implemented on `codex/p1-document-citations`,
executable0c43df1/base#1392b29546. Internal runtime helpers reuse existing authorized
pinned user/task section reads; exact normalized nonblank quote<=4000codepoints,
object/observation/root/segment/slot/page/global offsets and UTF8hash checked. No
new API/Store wire/model tool/source activation or broader task capability. Matches
retain actual partial/stale/history/inspection freshness, not drafting permission.
40new focused casesPASS; full combined disposable backend1224PASS/zero skips/
2existingwarnings76.31s. Ruff/format197files/links/docformat/diffPASS; existing M
code, schemas, model tool registration and draft paths preserved.
[Evidence](docs/P1-DOCUMENT-CITATIONS.md). M has no new handoff and retains#136
inactive Chrome host claim. Review requested when available; P0reviews#139/#46
remain pending. No monitor/browser/provider/model/send/spend/grant/install/retained
migration/worker/deploy/mainmerge. P1 remains open.
