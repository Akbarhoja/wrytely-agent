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

| Step/component           | Owner             | State and evidence                                                                         | Next action/blocker                                                               |
| ------------------------ | ----------------- | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| Revision7 planning / #44 | A                 | Code/PR audit and ordered work orders prepared; docs only                                  | Counterpart review; new interfaces still proposals                                |
| P0-A1 baseline           | A                 | codex/p0-baseline combines #40/#42, revision7 and M Canvas proposal; main not consolidated | CI391/114 plus M independent local391/114 pass; human approval still needed       |
| Diagnostics #40          | A                 | ddd5ab1, scoped counterpart review;381 backend/113 web CI reported                         | Included in #46; not deployed                                                     |
| Pause recovery #42       | A                 | 224bc96 (code a7db006), scoped review;385 backend/113 web CI reported                      | Included in #46; combined CI391/114 passed, review pending                        |
| Murtazo #28              | M                 | a344642 UI; latest a383782 Canvas proposal;114 local web reported                          | Reuse proposal findings; extension supersedes initial OAuth path                  |
| P0-A2 Meta               | A                 | Basic M1 response worked; last live M2 failed NotFoundError before draft                   | Two-call probe passed (see #50); failed-call reservation retained                 |
| P0-M1 Canvas             | M                 | M started #51 offline Canvas feasibility; live same-session access pending                 | Consenting exact CSU origin/course scope and install authorization requested by M |
| P0-M2 Outlook            | M                 | M #54 at4aadc91 offline Graph probe;32 cases independently pass                            | Real consent, email/attachment and notification evidence pending                  |
| P0-M3 WhatsApp           | M                 | Linking/inbound worked; last delivery failed131031                                         | Business/account resolution and delivered-reply proof                             |
| P0-A3 interfaces         | A                 | C1/C2 agreed atccf84dc; RFC3339 offset fix10b8625; C3–C7 still proposals                   | M agreement6537274371 recorded; P1-A1 lifecycle implementation needs review       |
| P1 collection/memory     | A/M by work order | P1-A1 #58 Canvas lifecycle storage implemented; automatic collectors absent                | 459 local backend pass; M review; sync transactions + Outlook secrets pending     |
| P2 always-on ownership   | A/M by work order | Existing task worker; continuous workers stopped                                           | Supervisor, schedule, hard budgets and bounded deployment                         |
| P3/P4 work/adaptation    | A/M by work order | Private drafting/checks scripted; live artifact not produced; A4 parked                    | Real accepted work/delivery, revisions and follow-through                         |
| P5/P6 pilot/release      | A/M by work order | Not started                                                                                | Reliability, live evidence and release approval                                   |

P1-A1 first slice: full disposable-local-Postgres suite **459 passed**, including38
connection-lifecycle cases and30 digest cases; Ruff lint/format and doc/diff checks pass.
Migration010 was applied only to disposable tests, not Railway. No route or collector wired.

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

A: #58 P1-A1 lifecycle review, then sync/source atomic persistence; keep P0 live gates open.
M: #56 offline digest helper independently28 pass; Canvas/Outlook live access and WhatsApp recovery.
Claims must be posted in #4 before implementation. Nobody takes over the other's files.

[Historical detailed status](docs/archive/STATUS-through-2026-10-29.md) preserves
prior runs, authorizations and limitations. Old stage documents are context; this
revision's scope and work orders determine new implementation.
