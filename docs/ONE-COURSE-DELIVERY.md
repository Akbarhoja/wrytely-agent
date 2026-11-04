# One-course autonomous submission — November 3, 2026

Supervisor approved this delivery scope in chat. Target: November 4, 2026 at 7:00 PM America/Denver (9:00 PM ET), verified
on the [event page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) November 3.
Feature freeze target: November 4 at 3:00 PM Mountain; recording/upload by 5:00 PM.
Organizers require open-source GitHub and emphasize the three-minute demo video.
This supersedes the stop-before-P2 instruction. Keep the existing Python runtime,
Meta primary reasoning, Store, Canvas collector/journal and private result pipeline.
No Hermes/OpenClaw/Muse Personal Agent migration. Full semester vision remains the
roadmap; this submission is explicitly a one-course prototype.

## Required student journey and execution order

1. Connect Canvas; discover courses automatically; choose exactly one course for the
   submission scenario. Read available syllabus, assignments, announcements and
   relevant documents, with honest coverage gaps. Existing approved two-course test
   may finish; this plan does not change its live scope automatically.
2. Enable course supervision explicitly. Cloud supervisor inspects stored evidence,
   chooses what to investigate, offers help or waits, and persists its next check.
   No student prompt is needed for each decision. Model chooses actions within typed
   tools; source content cannot grant permissions. Browser-off means stored evidence,
   not unseen Canvas updates. New source versions trigger reassessment.
3. Student receives an evidenced offer on WhatsApp; acceptance binds current source
   versions to the existing private draft workflow. No automatic permission to draft
   from reading an assignment. Offer and acceptance are idempotent.
4. Meta prepares and checks an appropriate draft/preparation result. Deliver a private
   usable file, accept a revision, retain both versions and repeat checks. Labs request
   real student results. Never open/solve timed quiz attempts or submit coursework.
5. On changed deadline/instructions after a successful sync, reconsider the plan,
   invalidate stale offers and explain the changed priority. Demonstrate this with a
   labeled synthetic change if no real authorized course change exists.
6. Prove restart/pause, one-account scope, cross-account denial, bounded calls/costs,
   no duplicate offers/work, unknown-call/send handling and one laptop-closed decision.
   Record the real duration; 72-hour soak and broader pilot remain pending roadmap work.
7. Record demo and prepare repository/setup/Meta-use evidence while engineering runs.
   Freeze the candidate several hours before the verified cutoff; upload early.

## Exactly one implementation owner per area

A (Akbar/Codex), branch codex/p1-completion: remaining P1 fixes/live acceptance;
runtime/supervisor.py, shared/course_supervision.py, contracts/course_supervision.py,
additive 023 migration, related tests and contracts. Reuse task planner/drafting;
add persisted course decisions/offers/checks, scoped evidence investigation, acceptance
handoff and later rendering/revision. Own shared documentation and integration review.

M (Murtazo), separate branch from current shared candidate: app/ HTTP/inbound assembly,
integrations/whatsapp*, app/whatsapp_worker.py, deploy/ and student web controls/results.
Begin P2/P3 transport/service assembly now; earlier P1-overlap pause does not prohibit
this assignment. Do not edit A's supervisor/store/contracts/collector. First inspect
WhatsApp restriction status without changing business/legal details; report exact safe
blocker. Wire approved reply-template opt-in separately from proactive-offer authorization;
never repurpose reply-only consent for proactive sends. Implement offer/accept/revision
routing using A's published Store boundary, prepare continuous-process entrypoint and
health/stop controls, and prepare reproducible demo/setup materials. Send interface
incompatibilities/findings immediately; no ceremonial agreement wait.

A publishes concrete executable boundaries as implemented. M can prepare assembly
against their signatures, but must not claim placeholders are live. Do not create a
parallel runtime/store/journal. M's empty-all_active refresh finding is A-owned.

## Activation and acceptance

Code implementation is authorized now. Existing live scope and $2 total ceiling
remain; $150 credits are not a replacement budget. New retained migrations, deployment,
paid cloud supervision and outward sends need applicable scoped activation approval
once the tested candidate and concrete budget are ready. No broad production launch.
Meta-business/legal decisions remain Akbar's. WhatsApp failure remains a submission
blocker unless Akbar explicitly selects a disclosed website fallback and rules allow it.

Outlook, Teams/group chat, calendar, handwriting, all-format parsing, multi-course
priority proof, grade recovery, broad pilot and 72-hour soak are later delivery scope.
Do not label original P0–P6 complete from this one-course demonstration. Release claims
must identify built, scripted-tested, live-proven and blocked capabilities separately.

## November 3 implementation checkpoint

A supplies persisted scoped supervision/Meta decisions/evidence inspection, offers,
source-event wakeup, original-outbox proactive authorization and independent enqueue
recovery, cumulative dollar caps/unknown holds, checked DOCX/private revisions and
typed checked-attachment authority. Read-only connection/course lookup recovers an
existing monitor without enrolling/resuming it. Exact APIs and tests are published
in docs/contracts/COURSE-SUPERVISION-v1.md, COURSE-OFFER-DELIVERY-v1.md,
MODEL-BUDGET-v1.md, ARTIFACT-REVISION-v1.md and ARTIFACT-DELIVERY-v1.md.

M017946f/785149e/fcccc19 HTTP, student controls, typed dispatch, document media,
recovery and budgeted-service assembly is reviewed and combined. M0bafa22 signed
slash-command parser/webhook and bae6085 connected signed-ingress rehearsal are
also imported exactly, preserving authorship. The real Store/runtime/transport
journey exercises signed accept, file, revision, replay and receipt paths with
scripted model/provider responses. This is not external provider acceptance.

Executable `92568ab` is the combined candidate. Its dedicated realPostgres integration
step plus web/build/extension/diagnostic jobs pass in run 41752360843; full backend
regression is now SUCCESS (1834 tests plus346 focused checks). Earlier
`1c4b6e0` full run 41742559685 is SUCCESS, but does
not cover the newest signed assembly/partial-inspection change. Local 146 web,
TypeScript/format and pure schema checks pass. Detailed evidence is in STATUS.

Actual newest Canvas connection still reports partial assignments/announcements/
grades/modules, restricted files and open submissions/syllabus for ECE253. Current
partial originals can be inspected with explicit missing reasons; work offers,
drafting, citation and delivery still require their original complete/current
checks. Real course action readiness is not established. Owner submitted Meta
business verification; under review, not approved. Real Meta decisions/quality,
phone file receipt/native layout, restart/laptop-closed duration, demo and submission
remain. The later approved bounded activation deployed023–028 and ran one incomplete
Meta request; monitor paused, budget disabled, no send. See the execution record.

The completed bounded activation is documented in
[the bounded development check](ONE-COURSE-LIVE-CHECK.md). It records Akbar's approved,
executed and stopped check; it does not authorize a repeat.
