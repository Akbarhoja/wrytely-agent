# Engineering status

Updated October 30, 2026. [Plan revision7](docs/BUILD-PLAN.md) ·
[Work orders](docs/WORK-ORDERS.md) · [Code audit](docs/IMPLEMENTATION-AUDIT.md) ·
[Team coordination](https://github.com/Akbarhoja/wrytely-agent/issues/4)

## Product decision and actual stage

Own Wrytely runtime + Meta primary intelligence. Required first version: Canvas
extension + Outlook email + WhatsApp, automatic discovery and semester supervision,
checked delegated work, revisions and follow-through. Hermes deferred. Cloud agent
must stay available while laptop is off; Canvas collection still depends on browser
and session availability. No manual-paste substitute for connector completion.

We are at **P0: live access gates open; P1 storage implementation started**, with reusable
task/draft foundations. No completed
24/7 academic agent, Canvas extension, Outlook connection or semester supervisor yet.
Historical M1/M2 live gates remain incomplete; renumbering the plan does not pass them.

## Current work and evidence

| Step/component           | Owner             | State and evidence                                                                         | Next action/blocker                                                                 |
| ------------------------ | ----------------- | ------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| Revision7 planning / #44 | A                 | Code/PR audit and ordered work orders prepared; docs only                                  | Counterpart review; new interfaces still proposals                                  |
| P0-A1 baseline           | A                 | codex/p0-baseline combines #40/#42, revision7 and M Canvas proposal; main not consolidated | CI391/114 plus M independent local391/114 pass; human approval still needed         |
| Diagnostics #40          | A                 | ddd5ab1, scoped counterpart review;381 backend/113 web CI reported                         | Included in #46; not deployed                                                       |
| Pause recovery #42       | A                 | 224bc96 (code a7db006), scoped review;385 backend/113 web CI reported                      | Included in #46; combined CI391/114 passed, review pending                          |
| Murtazo #28              | M                 | a344642 UI; latest a383782 Canvas proposal;114 local web reported                          | Reuse proposal findings; extension supersedes initial OAuth path                    |
| P0-A2 Meta               | A                 | Basic M1 response worked; last live M2 failed NotFoundError before draft                   | Two-call probe passed (see #50); failed-call reservation retained                   |
| P0-M1 Canvas             | M                 | M #64 lifecycle API reviewed/21 cases pass; local diagnostic work reported                 | Full redacted access/session/content acceptance evidence not yet reviewed           |
| P0-M2 Outlook            | M                 | M #54 at4aadc91 offline Graph probe;32 cases independently pass                            | Real consent, email/attachment and notification evidence pending                    |
| P0-M3 WhatsApp           | M                 | Linking/inbound worked; last delivery failed131031                                         | Business/account resolution and delivered-reply proof                               |
| P0-A3 interfaces         | A                 | C1/C2 agreed atccf84dc; RFC3339 offset fix10b8625; C3–C7 still proposals                   | M agreed scope/actor6537874178; context/discovery implementation under review       |
| P1 collection/memory     | A/M by work order | P1-A1 #58 adds staged academic text/check/event transactions; collectors not assembled     | 548 local backend pass; counterpart review + fresh retrieval/segments still pending |
| P2 always-on ownership   | A/M by work order | Existing task worker; continuous workers stopped                                           | Supervisor, schedule, hard budgets and bounded deployment                           |
| P3/P4 work/adaptation    | A/M by work order | Private drafting/checks scripted; live artifact not produced; A4 parked                    | Real accepted work/delivery, revisions and follow-through                           |
| P5/P6 pilot/release      | A/M by work order | Not started                                                                                | Reliability, live evidence and release approval                                     |

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

Shared PDF packaging #75 provides pypdf6.21.4 for M's requested future extractor; exact
version and hashes are in uv.lock. Locked install, trusted synthetic text-PDF smoke,
unchanged existing-version audit and full585 backend tests pass. The proposed subprocess/memory/CPU/wall
boundary is in docs/contracts/PDF-EXTRACTION-BOUNDARY.md and awaits M agreement.
No PDF extractor or document-segment/reader activation is included.

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

A: #71/#72 storage review and #73 freshness review; agree C3 retrieval/segments, then implement owned readers.
M: assemble accepted lifecycle/context consumers; source extraction and Canvas/Outlook live evidence; WhatsApp recovery.
Claims must be posted in #4 before implementation. Nobody takes over the other's files.

[Historical detailed status](docs/archive/STATUS-through-2026-10-29.md) preserves
prior runs, authorizations and limitations. Old stage documents are context; this
revision's scope and work orders determine new implementation.
