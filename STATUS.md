# Engineering status

Updated October 31, 2026. [Plan revision7](docs/BUILD-PLAN.md) ·
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

| Step/component           | Owner             | State and evidence                                                                         | Next action/blocker                                                                         |
| ------------------------ | ----------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| Revision7 planning / #44 | A                 | Code/PR audit and ordered work orders prepared; docs only                                  | Counterpart review; new interfaces still proposals                                          |
| P0-A1 baseline           | A                 | codex/p0-baseline combines #40/#42, revision7 and M Canvas proposal; main not consolidated | CI391/114 plus M independent local391/114 pass; human approval still needed                 |
| Diagnostics #40          | A                 | ddd5ab1, scoped counterpart review;381 backend/113 web CI reported                         | Included in #46; not deployed                                                               |
| Pause recovery #42       | A                 | 224bc96 (code a7db006), scoped review;385 backend/113 web CI reported                      | Included in #46; combined CI391/114 passed, review pending                                  |
| Murtazo #28              | M                 | a344642 UI; latest a383782 Canvas proposal;114 local web reported                          | Reuse proposal findings; extension supersedes initial OAuth path                            |
| P0-A2 Meta               | A                 | P0 real tool/saved-result/continuation proof passed in #50; academic M2 remains open       | Two-call probe passed (see #50); failed-call reservation retained                           |
| P0-M1 Canvas             | A (reassigned)    | M #64 lifecycle API reviewed/21 cases pass; local diagnostic work reported                 | Full redacted access/session/content acceptance evidence not yet reviewed                   |
| P0-M2 Outlook            | A (reassigned)    | M #54 at4aadc91 offline Graph probe;32 cases independently pass                            | Optional/paused: CSU admin consent required; not a core stage blocker                       |
| P0-M3 WhatsApp           | M                 | Linking/inbound worked; last delivery failed131031                                         | Business/account resolution and delivered-reply proof                                       |
| P0-A3 interfaces         | A                 | C1/C2 and C3 short-text design agreed; remaining C4–C7/precise document wire gates open    | Reader fix #98 accepted by M; document/schema2 wire details remain separate                 |
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

P0 core checkpoint: Meta access proof passed. A owns Canvas feasibility; the current
signed-in dashboard is available, but the diagnostic's detailed resource report/session
matrix is still pending. Operator was asked to supply the existing counts-only report;
browser controls cannot open Chrome extension-management pages. No restart/logout was
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

## Next actions

A: obtain #97 Unicode fix review, review/integrate agreed components and add discovery
Node CI on a branch containing the actual extension. Complete reader/long-document
and supervisor work in their ordered reviewed slices; no live source activation yet.
M: P0 access evidence/blockers; claimed integration work and agreed cross-layer tests.
Claims must be posted in #4 before implementation. Nobody takes over the other's files.

[Historical detailed status](docs/archive/STATUS-through-2026-10-29.md) preserves
prior runs, authorizations and limitations. Old stage documents are context; this
revision's scope and work orders determine new implementation.
