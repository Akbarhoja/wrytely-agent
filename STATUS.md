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

We are at **P0: baseline/access**, with reusable task/draft foundations. No completed
24/7 academic agent, Canvas extension, Outlook connection or semester supervisor yet.
Historical M1/M2 live gates remain incomplete; renumbering the plan does not pass them.

## Current work and evidence

| Step/component           | Owner             | State and evidence                                                                         | Next action/blocker                                                          |
| ------------------------ | ----------------- | ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| Revision7 planning / #44 | A                 | Code/PR audit and ordered work orders prepared; docs only                                  | Counterpart review; new interfaces still proposals                           |
| P0-A1 baseline           | A                 | codex/p0-baseline combines #40/#42, revision7 and M Canvas proposal; main not consolidated | CI391 backend/114 web passed at9bbea97; #46 counterpart/human review pending |
| Diagnostics #40          | A                 | ddd5ab1, scoped counterpart review;381 backend/113 web CI reported                         | Included in #46; not deployed                                                |
| Pause recovery #42       | A                 | 224bc96 (code a7db006), scoped review;385 backend/113 web CI reported                      | Included in #46; combined CI391/114 passed, review pending                   |
| Murtazo #28              | M                 | a344642 UI; latest a383782 Canvas proposal;114 local web reported                          | Reuse proposal findings; extension supersedes initial OAuth path             |
| P0-A2 Meta               | A                 | Basic M1 response worked; last live M2 failed NotFoundError before draft                   | Reconcile usage, diagnose with safe metadata; no blind retry                 |
| P0-M1 Canvas             | M                 | Proposal only; extension/same-session access untested                                      | Claim feasibility step; consenting course scope                              |
| P0-M2 Outlook            | M                 | Required now; no implementation/live access                                                | Claim Microsoft authorization feasibility                                    |
| P0-M3 WhatsApp           | M                 | Linking/inbound worked; last delivery failed131031                                         | Business/account resolution and delivered-reply proof                        |
| P0-A3 interfaces         | A                 | C1–C7 v1 proposals published (#47/#48); all await owner agreement                          | Agree with M before dependent coding                                         |
| P1 collection/memory     | A/M by work order | Existing versioned snapshots; automatic collectors absent                                  | Connection/sync/freshness contracts and source readers                       |
| P2 always-on ownership   | A/M by work order | Existing task worker; continuous workers stopped                                           | Supervisor, schedule, hard budgets and bounded deployment                    |
| P3/P4 work/adaptation    | A/M by work order | Private drafting/checks scripted; live artifact not produced; A4 parked                    | Real accepted work/delivery, revisions and follow-through                    |
| P5/P6 pilot/release      | A/M by work order | Not started                                                                                | Reliability, live evidence and release approval                              |

Counts above belong to their cited commits and historical runs, not a fresh full
suite on the revised planning branch. Current source/status two-account live denial
checks passed previously; live artifact isolation remains untested because no live
artifact exists. Read the [actual M2 run](docs/M2-RUN-2026-10-29.md).

## Operating limits retained

Last verified deployment: isolated Railway API, code1dcb4d3; migrations001–007 +009,
not008. No continuous reasoning/delivery worker enabled. No production release.

Historical known Meta usage$0.00773075 plus unknown-use reservation$1.32 =
$1.32773075 charged/reserved against the existing$2 total ceiling. This is not a
fresh billing statement. Available$150 credits are not new spending authorization.
Existing M2 allowance was one synthetic workflow, <=10 requests and <=$1.50 within
that$2 ceiling, no WhatsApp sends, workers stopped. Reconcile before another call;
a continuous pilot needs its own explicit limit/activation scope.

## Next actions

A: P0-A1 reviewed consolidation; P0-A2 safe diagnosis; P0-A3 shared interfaces.
M: P0-M1 Canvas extension feasibility; P0-M2 Outlook access; P0-M3 WhatsApp recovery.
Claims must be posted in #4 before implementation. Nobody takes over the other's files.

[Historical detailed status](docs/archive/STATUS-through-2026-10-29.md) preserves
prior runs, authorizations and limitations. Old stage documents are context; this
revision's scope and work orders determine new implementation.
