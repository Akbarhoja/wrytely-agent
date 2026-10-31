# Ordered engineering work orders

Revision 7 · October 30, 2026. Scope: [BUILD-PLAN.md](BUILD-PLAN.md).
Status: planned unless [STATUS.md](../STATUS.md) links acceptance evidence.
A = Akbar with Codex; M = Murtazo. Each item has exactly one accountable engineer;
the other reviews. Akbar's account/legal/product decisions are separate from M's
technical ownership. No item grants new live permissions or spending automatically.

## Execution rules

1. Read AGENTS.md, TEAM.md, STATUS.md, CONTRACTS.md, this work order, and issue #4.
2. Claim one item in GitHub with owner, exact branch/base, file list, dependencies and
   acceptance. Existing claims cannot be duplicated. Do not push another owner's branch.
3. Agree changed interfaces before dependent implementation. A owns storage/schema/contracts;
   M owns HTTP/provider assembly. M requests shared methods, never creates a parallel store.
4. Implement one coherent slice, focused tests, applicable CI and opposite-owner review.
   A large work order can use several small sequential PRs under the same owner.
5. Record evidence as code/scripted/live separately. Exact combined-head tests are required
   after integration; component suites do not prove the assembled system works.
6. Update one status row and post a concise handoff in #4: interface, commit, evidence,
   remaining blocker and next eligible item. Never take over because the other person waits.

October31 latest supervisor decision returns P0-M1 and P0-M2 to Murtazo; the
intermediate #79 reassignment to A is superseded. P0-M3 also remains M. A retains
P0-A1/A2/A3 and owned runtime/shared work. See [current ownership](../TEAM.md#current-p0-ownership--october-31-2026)
and [safe handoff](P0-ACCESS-2026-10-31.md). Checkpoint active P1 work, then prioritize
P0 access evidence/explicit blockers. P1+ implementation owners are unchanged.

## P0 — Establish the baseline and prove access

### P0-A1 — Consolidate reviewed work (A)

Depends: current #4 review state. Files: owned integration branch and integration evidence;
merge reviewed commits without rewriting M's implementation.

1. Inventory #36 candidate a8cac79 and constituent history; incorporate reviewed #40
   ddd5ab1 and #42 224bc96, then the updated #44 plan. Check current heads before acting.
2. Review M's #28 documentation a383782; preserve useful Canvas research while the new
   extension work order supersedes its initial cloud-OAuth assumption. Keep #24/A4 parked.
3. Resolve documentation conflicts without losing evidence; run combined CI and request
   counterpart review. Follow existing protected-main rules; no override or fake approval.
4. Record one exact shared base. After main receives the combined code, new branches
   start from main. Close redundant constituent PRs only after ancestry is verified;
   branch deletion is not necessary to complete consolidation.

Done when: combined code/tests are reviewed on a recorded head and main merge status
is explicit. If human approval is pending, keep that gate pending; independent access
spikes may proceed from their declared base.

### P0-A2 — Diagnose Meta and account for usage (A)

Depends: #40 safe diagnostics available. Files: shared/model_client.py, runtime/worker.py,
owned adapter/worker tests, redacted run evidence.

1. Reconcile known/unknown reserved usage; check authorized remaining budget.
2. Inspect actual provider request, model availability, account/endpoint and safe error
   evidence. Use currently documented APIs; do not blindly try endpoints or switch models.
3. If existing budget permits, run one bounded minimal real tool-call cycle and then a
   planner cycle. Preserve tool results and continuation; record actual/unknown usage.
4. Fix the specific failure and add regression coverage. Do not turn a provider error
   into a plausible model answer or disable required checks to get a green result.

Done when: real Meta tool call → saved tool result → model continuation succeeds within
budget. Account/catalog access alone and old basic reply success do not close this gate.

### P0-M1 — Canvas extension feasibility (M)

Depends: consenting account/origin/course scope and installation permission. Files:
new extension/ feasibility slice, owned tests, docs/spikes/canvas-extension.md.

1. Test read-only same-session access in the exact CSU Canvas origin, with tab open,
   tab closed/browser running, browser restart, expired login and account switch.
2. Discover courses and read one real syllabus document, assignment/rubric and discussion
   with pagination. Record whether background access works and what requires an open tab.
3. Inspect minimum host permissions and session behavior; no cookie/password export,
   hidden-content bypass or writes to unlock discussions. Use synthetic fixtures in Git.

Done when: redacted evidence classifies access as background/tab-required/blocked and
identifies content gaps. A successful course-list request alone is insufficient.

### P0-M2 — Outlook feasibility (M)

Depends: consenting mailbox and Microsoft app/consent access. Files: integrations/outlook/
spike and docs/spikes/outlook-access.md; shared storage is not implemented here.

1. Verify delegated read access for the actual school account; document admin approval
   blockers. Test mail content/attachment access, incremental reads and subscription support.
2. Specify OAuth state/PKCE/callback, offline refresh requirements, renewal and revocation.
   No Mail.Send permission or Outlook UI scraping substitution.
3. Choose relevant folder coverage and explain that notifications alone are not the email
   contents. Design delta recovery for missed events and expired cursors.

Done when: exact consent/access results and minimal requested scopes are recorded.
Unavailable consent stays an Outlook blocker; fixture work proceeds without claiming access.

### P0-M3 — WhatsApp live delivery (M)

Depends: business/account setup and consenting recipients. Files: existing integrations/
whatsapp*, app/whatsapp_worker.py and owned transport/API tests.

1. Diagnose 131031 on the actual account; request only the human business/legal step needed.
2. Confirm webhook/subscription/link and delivery status with the official Cloud API.
3. Identify actual template approval requirements for proactive outreach; do not assume
   a generic template is approved or a replacement number fixes an account-level lock.

Done when: a real consenting phone receives a reply and signed status confirms delivery.
A Telegram test is separate evidence, not completion. New sends remain within consent.

### P0-A3 — Freeze interfaces and operational limits (A)

Depends: M reviews proposals; P0 access findings refine them. Files: CONTRACTS.md,
new contract models/fixtures and additive migrations when ready; M only reviews here.

1. Define C1–C7 below with M: payloads, trusted identity, errors, generations, rollback,
   quotas and ownership. Include examples and replay/negative cases before consumer coding.
2. Plan additive wrytely_agent migrations against the actual ledger (001–007 and009;
   008 belongs to parked A4). No reused migration number or modification of applied SQL.
3. Design per-call/account/global cost reservations and a live activation/stop procedure.
4. Record migration and rollback order. Protocol proposals do not rename existing APIs.

Done when: both owners agree exact contracts and fixtures; budgets/configuration defaults
are bounded. Contracts are versioned and links to approvals are recorded.

## Shared interface checklist (proposed, not executable yet)

| ID            | A supplies                                                                                              | M consumes/supplies                                                         | Required invariant                                                                                                                                          |
| ------------- | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1 connection | Pairing, scoped credential hashes, encrypted Outlook secret handles, generation/revoke, safe projection | Pairing UI, OAuth/provider identity verification and authenticated assembly | Never derive student identity from posted owner ID; reconnect fences prior device/provider state                                                            |
| C2 sync       | Begin/commit/checkpoint operations; per-resource coverage/freshness; atomic durable events              | Canvas batches, Outlook delta/notification batches                          | Envelope has schema version, connection generation, batch/replay key, object IDs/digests, observation times and completeness; no deletion from partial scan |
| C3 memory     | Scoped source list/search/section retrieval and private commitment projection                           | Coverage/source display                                                     | Immutable versions plus separate last_checked; original evidence reachable from every extracted fact                                                        |
| C4 actions    | Durable offer/message/file intents, authorization, quotas and cancellation                              | Typed WhatsApp adapter/worker and signed receipts                           | Separate accepted/delivered/unknown; scope recipient, offer, revision and connection generation                                                             |
| C5 decisions  | Accept/decline/self/snooze/revise controls and persistent intent                                        | Authenticated text/button routing from verified link                        | Duplicate/stale/cross-account input cannot grant work or delivery scope                                                                                     |
| C6 files      | Owned versioned artifact renderer/storage interface and authorized download projection                  | Private upload/document delivery and web result consumer                    | Same artifact revision checked, rendered and sent; no public stable file URL                                                                                |
| C7 operations | Budget/fair queue/worker health and restart semantics                                                   | Process topology, health/alerting/deployment assembly                       | Persist before notifying; stops/revocation honored at side-effect boundaries; no blind unknown-send retry                                                   |

Source keys include institution/mailbox and connection namespace, not only course ID.
Version digest and last_checked are separate. OAuth callbacks, extension data and
webhooks require their appropriate verification; a contract example is not authority.

## P1 — Automatic collection and usable memory

### P1-A1 — Connection and sync persistence (A)

Depends: P0-A3 C1/C2. Files: shared/ connection/sync stores, contracts/ models/SQL,
shared/db.py composition and owned tests.

Implement private pairing/credential lifecycle, connection generations, encrypted
Outlook credential references, bounded sync claims/batches, checkpoints and atomic
source/event persistence. Reuse Store and observe_source rather than a second DB layer.
Bound request sizes/counts and reject replay with changed data, stale generation and
older snapshots. Support deletion evidence separately from missing data.

Done when: two-account, expired pairing, duplicate upload, partial scan, interrupted
batch, reconnect and disconnect-race tests pass; retries resume without duplicate events.

### P1-M1 — Pair and build the Canvas collector (M)

Depends: P0-M1; P1-A1 accepted C1/C2. Files: extension/, integrations/canvas/, app/ source
assembly and owned tests. Existing app/main.py assembly remains M-owned.

Implement paired auth and sync routes, stable course enumeration, paginated syllabus,
assignments/rubrics/effective dates, announcements, discussions/replies, modules/pages,
submission/grade reads and authorized file-content extraction. File listings do not
count as read contents. Resume a durable local checkpoint across worker suspension;
sync on startup/availability and approximately 30-minute opportunities with backoff.
Validate origins/redirects, bounded downloads and HTML conversion; never execute content.
Handle hidden/initial-post-required/external-system content as coverage limitations.

Done when: two controlled courses automatically collected without manual IDs; repeat
sync creates no new content/events; changed item appears once; session expiry and
browser restart resume accurately. Real CSU validation and synthetic fixture tests
are separately labeled. Requested scopes/content must match consenting access.

### P1-M2 — Outlook cloud ingestion (M)

Depends: P0-M2; P1-A1 C1/C2. Files: integrations/outlook/, app/ OAuth/webhook/poll assembly,
owned tests. A implements any newly needed shared method first.

Implement authorized OAuth connection and identity binding, safe refresh, notifications,
subscription renewal, per-folder delta checkpoints and catch-up polling. Collect full
relevant messages/attachments with provenance; deduplicate moves/notifications and
handle invalid delta state by a bounded rescan. Do not assume subject alone identifies
an assignment. Keep collection/relevance scope visible and disconnect effective.

Done when: with laptop off, a real test email reaches private evidence; duplicate/lost
notifications, token expiry, subscription renewal and disconnect are covered.

### P1-A2 — Freshness, retrieval and change events (A)

Depends: P1-A1 and representative M collector fixtures. Files: shared/academic_memory.py,
new scoped retrieval/event helpers, runtime/draft_requirements.py, runtime/drafting.py,
runtime/verification.py, related shared preflights and contracts/tests.

Separate last_checked from immutable versions. Replace scattered 24-hour checks with
one policy based on evidence type, coverage, decision and urgency, retaining stale-write
fences. Segment long sources and retrieve original sections without silently truncating;
replace reliance on eight sources/6,000-character summary limits through bounded paging.
Emit structured field changes and content-changed events; Meta later interprets free text.

Done when: unchanged successful sync refreshes status without new version/offer; partial
sync cannot certify full coverage; stale urgent facts request refresh; all preflight and
final-commit consumers agree; long-file citation retrieval and cross-account denial pass.

### P1-M3 — Connections and course coverage UI (M)

Depends: P1-A1/A2 projections and P1-M1/M2. Files: web/, app/ private read assembly.

Build install/link/unlink, Outlook connect/reconnect, course discovery and per-resource
coverage/freshness views. Explain tab-required collection if applicable. Keep manual
snapshots as explicit troubleshooting, remove manual assignment entry as normal onboarding.

Done when: a student can connect, see actual discovered courses and gaps, reconnect and
unlink. UI cannot report a failed/partial scan as fully up to date.

## P2 — The agent takes initiative and stays available

### P2-A1 — Commitments and semester supervisor (A)

Depends: P1-A2 C3/C5; fixtures may unblock implementation before live sources. Files:
runtime/ supervisor/tools, shared/ commitment/goal stores, contracts/ and tests.

Create evidenced commitments and deduplicate across sources. Separate tracking, permission,
work/result state and submission evidence rather than one overloaded status. Supervisor
retrieves details, compares courses, sets goals, chooses bounded actions and examines tool
results. Reuse current per-responsibility planner as a worker underneath the supervisor.
Create no automatic drafting permission from a source. Persist reason/wait/next action.

Done when: competing deadlines cause a reasoned offer without a student prompt; optional
posts do not become tasks; ambiguous email matching requests clarification; no-progress
loops stop within limits; task completion/failure resumes supervisor appropriately.

### P2-A2 — Durable schedules, action ledger and budgets (A)

Depends: P0-A3 C4/C7, P2-A1. Files: runtime/, shared/ task/delivery/budget modules,
contracts/ and tests; no M transport edits.

Add persisted next checks, event coalescing, fair account scheduling, leased supervision,
retry/backoff and budget reservations. Extend existing outbox beyond completed text replies
for proactively authorized offers. Cancel obsolete schedules, honor pause/disconnect/quiet
hours, cap unsolicited messages (initial default three/day), allow silence and bundle updates.
Message count and reminder timing are product settings, not unlimited model discretion.

Done when: restart restores due work; repeats do not duplicate intents; revoked controls
fence late results; unknown usage stays reserved; account/global cost ceilings stop dispatch.
Unknown external-send results never trigger blind retry. Operator can stop all paid work.

### P2-M1 — Proactive WhatsApp transport (M)

Depends: P0-M3, P2-A2 C4; can prepare adapters against agreed fixtures. Files:
integrations/whatsapp*, app/whatsapp_worker.py, transport tests.

Consume validated proactive intents, implement approved notification/offer templates
and receipt handling. Current approved-reply template support is not automatically a
proactive-offer contract. Bind callbacks to configured business/link/offer and preserve
unknown results. Never invent a template approval or bypass conversation-window controls.

Done when: actual linked test phone receives an agent-originated offer, including an
approved template after >24 hours without inbound messages; delivery evidence is recorded.

### P2-M2 — Continuous development service (M)

Depends: P0 baseline, P1-M2, P2-A1/A2/M1, explicit bounded activation budget/scope.
Files: deploy/, app/ process entrypoints/health, operational runbook and owned tests.

Run separate API, reasoning worker, connector scheduler and WhatsApp delivery processes
as needed, reusing services rather than introducing another runtime. Configure restart,
queue-age/last-success health, provider outage reporting and a stop mechanism. A supplies
runtime/budget semantics; M owns deployment assembly. Start on isolated development only.

Done when: laptop-closed Outlook update produces supervisor decision and real WhatsApp
offer with no website visit; service restart preserves work. Record duration/cost/results,
then stop at the authorized bound. This early proof is required before calling it always-on.

## P3 — Complete delegated work

### P3-A1 — Interpret decisions and run academic work (A)

Depends: P2, C5; M provides verified inbound events. Files: runtime/ intent/tools/planner,
shared/draft_intents.py and related stores/contracts/tests.

Map buttons and free text to current work; ask when ambiguous. Student acceptance binds
a goal, sources, work scope and delivery permission. Reuse requirements/drafting/checks;
add capability assessment and tutoring/preparation paths for work requiring student input.
Expand tool access and continuation deliberately, never blanket-enable shell/submission.

Done when: duplicate acceptance produces one workflow; stale acceptance rechecks current
requirements; a lab requests real results and offers prep; policy/evidence failures explain
useful next action. A model may propose actions but cannot grant permission itself.

### P3-A2 — Render and revise private results (A)

Depends: P3-A1, C6 agreed. Files: runtime/ rendering/revision helpers, shared/artifacts.py,
contracts/ artifact types, owned tests; A owns renderer, M owns delivery/storage IO.

Produce Word/PDF from the checked artifact version, including cited evidence and required
disclosure; validate math/layout and open files. Store immutable version references and
checksums. Resolve revision target, preserve old version, apply requested change, rerun
checks and summarize changes. Use existing private artifacts, not public temporary links.

Done when: artifact body and delivered file correspond; v2 remains private and preserves
v1; files open on desktop/phone and supported math renders correctly. Unsupported content
is explicit rather than silently lost.

### P3-M1 — Student decisions, files and results (M)

Depends: P3-A1/A2 contracts and P2-M1. Files: integrations/whatsapp*, app/ assembly and
private file delivery/download, web/ result UI and owned tests.

Implement reply buttons plus authenticated free-text routing, short-lived authorized
file access and WhatsApp document delivery. Show version/check findings and waiting
reasons. Recheck current authorization at dispatch; expired/cross-account controls fail.

Done when: test phone accepts offer, receives a checked file, requests a revision and
receives v2; signed receipts and private result reads match the same version. No public
stable artifact URL and no app-local second intent interpreter.

## P4 — Adapt and follow through

### P4-A1 — Changed requirements and ongoing ownership (A)

Depends: P3 and P1 change events. Files: runtime/, shared/ memory/responsibility/schedule
modules, contracts/ migrations/tests. Review parked #24/A4 for salvage before copying.

Replace stop-only source invalidation with explicit reassessment while retaining stale
lease rejection. Determine affected goals/drafts, replan across courses, cancel old
reminders and revise inside existing consent/budget; request fresh delegation for material
scope expansion. Readiness is not submission; failed model work remains visible/recoverable.

Done when: extended deadline changes priorities without losing work; changed rubric blocks
stale delivery and leads to checked revision; unrelated source change does not restart all
work; duplicate changes and paused/revoked tasks cannot trigger repeated actions.

### P4-A2 — Progress, grade reasoning and completion (A)

Depends: P4-A1, grade/submission evidence from M. Files: runtime/ progress tools,
shared/ commitments/preferences, contracts/tests.

Implement deterministic grade calculations only with known weights, drop rules and grade
basis; show assumptions/unknowns. Meta proposes recovery plans and evidenced attendance
reminders. Follow up adaptively; distinguish self-reported done, observed submission,
resubmission and reopened assignments. Student preferences govern check-in frequency.

Done when: low-grade fixture leads to one sourced plan, unknown rules produce no invented
pass score, confirmed submission stops only its reminders, and reopened work remains tracked.

### P4-M1 — Completion evidence and controls (M)

Depends: P1 collection, P4 contracts. Files: integrations/canvas/, extension/, app/, web/
and owned tests. No grade-math or separate runtime implementation.

Complete provider mappings for student submission/grade/override states; expose fresh,
stale and conflicting evidence. Support pause, cancel, self-do, disconnect and reconnect
from agreed controls. Surface refresh requests and maintain existing accessible results.

Done when: next successful sync confirms the correct assignment submission; ungraded or
missing evidence is not treated as no submission; disconnected device callbacks cannot
revive work. Student can see and stop agent activity.

## P5 — Reliability and a small pilot

### P5-A1 — Integrated reliability and cost evaluation (A)

Depends: P4, approved live limits. Files: owned scenario/security/cost tests and redacted
acceptance reports. M supplies integration fixtures and runs their provider checks.

Run two-account isolation through source retrieval, model context, queues, files and
buttons; malicious source/email instructions, parallel jobs, expired leases, lost inference
responses, source races, restart, retries and cost caps. Trace actual Meta model usage.
Coordinate three full scenarios and a 72-hour controlled soak with a pre-agreed hard cap.

Done when: independent review sees exact build/config, failures and fixes, actual usage,
no cross-account access, no duplicate committed actions and honest ambiguous-send handling.
Scripted test counts alone do not pass real provider gates.

### P5-M1 — Connector/operation reliability and pilot UX (M)

Depends: P4 and A's acceptance harness. Files: extension/, integrations/, app/, web/,
deploy/ and owned tests/runbooks.

Test pagination, large attachments, browser suspension, account switch, OAuth revocation,
missed webhook/renewal, provider 429/outage, network loss and recoverable deploy rollback.
Exercise install/reconnect/unlink and approved data deletion/retention behavior. Prepare
synthetic courses; 3–5 consenting students try onboarding and agent interactions. Keep
classmate data out of public fixtures/demo. Verify original Wrytely remains unaffected.

Done when: operational recovery is demonstrated, top feedback issues resolved or explicitly
triaged, and no access failure appears as a successful empty sync.

## P6 — Release and truthful presentation

### P6-A1 — Release evidence and rule/provenance check (A)

Depends: P5. Files: README, final scorecard/disclosure, shared plan/status as needed.

Verify actual participant rules and submission eligibility; disclose third-party libraries,
prior auth/hosting/handwriting and new work. Confirm Meta performs primary runtime reasoning.
Review actual deployed acceptance, ongoing budget, rollback and remaining limitations.
Akbar makes public-release decisions; no rule-compliance guarantee from framework choice.

Done when: evidence supports every demo claim and the release decision is recorded.

### P6-M1 — Release preparation and demonstration (M)

Depends: P6-A1 review, release/account approvals. Files: deployment/setup docs, demo assets,
web/ production configuration and distribution instructions within approved scope.

Prepare reproducible extension installation/distribution, web/domain/auth configuration,
private storage and continuous services; record configuration without secrets. Demonstrate
controlled course discovery, email update, offer, checked work, revision and follow-through.
Label synthetic course data. Do not claim real university deployment from a sandbox demo.

Done when: approved release is reproducible and verifiable. Event submission happens only
under its actual deadline/rules; missing that date does not reduce the product scope.

## Immediate handoff after this planning PR

A: P0-A1 consolidation and P0-A2 diagnosis; draft P0-A3 interfaces using M's proposal.
M: P0-M1 Canvas extension feasibility, P0-M2 Outlook access and P0-M3 WhatsApp repair,
one explicitly claimed slice at a time. These assignments are queued, not claims that
M has started or agreed new interfaces. A must not implement those modules for M.
