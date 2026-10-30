# B2 — private academic snapshots

Owner: Murtazo. Branch: codex/b2-snapshot-intake, from reviewed 6accd71.
Coordination: #4 comments 6491647927 and 6491917360. Akbar approved the B2/A3
workflow while M1 provider setup is deferred. M1 remains incomplete. This work
order records the agreed direction. Shared snapshot reads are integrated; the
separate private-draft dependency still requires exact-head review.

## Student outcome and first slice

A signed-in student pastes an assignment, policy, source excerpt or controlled
group transcript into the existing workspace. The student can return to the
private saved snapshot and inspect its provenance. Saving context does not start
work. A later explicit delegation selects the sources and states the private
objective. A group transcript cannot itself authorize drafting or sharing.

Use the four fictional inputs in M2-ACADEMIC-SCENARIO.md for demonstration. Label
manual intake as a snapshot that does not monitor later changes. No Canvas,
Teams, URL fetcher or second conversation application is introduced. Full
commitment discovery and checked drafting require their separate agreed runtime
boundaries and integrated acceptance; snapshot intake alone does not complete B2.

## Architecture and ownership

Extend the existing FastAPI app, verified identity dependency, Store and Next
same-origin proxy. Keep student presentation inside components/workspace.tsx.
Reuse the existing design tokens, typography, panels, form and session patterns.

Murtazo owns app/main.py, optional new app/academic.py, tests/test_academic_api.py,
web/lib/forward.ts, web/tests/forward.test.ts, new web/lib/academic.ts,
web/components/academic-context.tsx, web/tests/academic-context.test.tsx,
web/components/workspace.tsx, web/tests/workspace.test.tsx, web/app/globals.css,
this work order and web/README.md.
Akbar retains shared storage/runtime/contracts and #26/#27 internal validation.
No shared implementation, migrations or STATUS.md edits are claimed here.

## Private result viewing slice

Reuse Store.responsibilities and the delivered responsibility_artifacts/artifact_review
reads. Add authenticated GET responsibilities (safe summary fields only),
responsibilities/{uuid}/artifacts (latest 50), and artifacts/{uuid}; no new mutation.
The existing workspace gets a Private results view with duty, saved draft and
check details. This does not consume the unreviewed private-draft authorization.

Owned files additionally include web/lib/results.ts, web/components/academic-results.tsx
and web/tests/academic-results.test.tsx, plus the existing claimed API/proxy/workspace
tests and styles. No model or database client is introduced.

Show saved text, disclosure, citation claims/quotations and stored review findings.
Ready for review requires current evidence, ready artifact state and a passed check.
Staleness overrides historical success; missing reports stay unchecked. A model
assessment remains fallible. Nothing is shared, sent, submitted or graded by viewing.
Plain-text rendering, private404, no-cache, real error/empty distinction and account
change/late-response guards remain mandatory. Verify using existing Store fixtures
and scripted assessments, followed by component/proxy tests and synthetic browser
checks. Real student/backend operator acceptance remains separate.

## Agreed shared dependencies

Existing Store.observe_source accepts SourceObservation. Ownership comes from
the verified session. The app sets coverage=snapshot and aware server retrieval
time. Existing source content limit is 24,000 characters; metadata must respect
the existing model bounds. References are labels, not fetched URLs.

The agreed new source_snapshots/source_snapshot methods provide private bounded
summaries/detail. Final serialization, current-version selection, ordering and
error behavior must be documented in CONTRACTS.md before consumer implementation.
List coverage is at most 50 items; no UI claim of a complete archive.

create_bound_responsibility must validate 1–8 owned sources and create all
bindings plus one initial plan in a single transaction. Worker/source-version
races must serialize. Same key/canonical source set/objective/step budget returns
the original duty; changed input conflicts. Failure rolls back. The app must not
compose create_responsibility followed by bind_source or rely on stopped workers.

Private responsibility_artifacts/artifact_review provide bounded saved results
and check reports. They must not expose leases, raw model histories, secrets or
another student's evidence. These are dependencies, not local substitute stores.

Full drafting additionally needs explicit persisted private-draft delegation,
source-backed policy/rubric assessment and atomic pre-claim task routing in the
runtime. A browser cannot supply authoritative CoursePolicy, readiness or action
permission. Unknown/conflicting policy blocks drafting. Until that boundary
lands, do not present analysis-only delegation as checked-draft authorization.

## API and student behavior to finalize before implementation

The first API slice will expose authenticated snapshot create/list/detail under
the existing /v1 namespace and proxy allowlist. Final request/response field names
must match the delivered shared contract. Reject owner, coverage, retrieval-time
and authority fields supplied by a browser. Preserve stable snapshot identity
and revision on a retry; conflicting reuse must not silently overwrite evidence.

No public route, automatic fetch, rich HTML rendering or browser storage of
academic content. Return no-store responses. Absent/not-owned detail is the same
404. Storage errors remain errors; they cannot become successful empty lists.
Enforce the existing proxy origin, JSON and byte limits and backend field bounds.

The form has visible labels, honest snapshot coverage, a separate save action,
and a readable saved-source list/detail. Preserve unsaved text during transient
errors within the current session; clear private state on identity changes.
An uncertain mutation is reconciled using its stable identity before retry.
Saving a source must not imply that a worker, model or message send ran.

## Acceptance and execution sequence

1. Inspect the delivered shared contract and tests; review source ownership,
   atomic binding, idempotency and response projection before consumption.
2. Write failing owned API tests for private intake/read, bounds, spoofed fields,
   replay/conflict, absent/not-owned and real storage errors. Implement using the
   existing Store; verify with disposable isolated Postgres.
3. Extend the existing proxy and test exact allowlisting, signed-out rejection,
   origin checks and no-cache responses.
4. Add the student form/list/detail using the existing workspace. Test retained
   drafts, failures, account switches and explicit save. Verify desktop/mobile
   layout and keyboard use with synthetic data.
5. Run focused tests, all backend tests, Ruff lint/format, web tests, TypeScript,
   formatting and production build. Record actual evidence and limits here.
6. Review through a separate B2 PR, linking the claim and exact shared dependency.
   Only add delegation/result presentation after their specific gates pass.

No live provider calls or message budget is authorized by this work order.
No deployment, production migration, public signup, sharing or submission.
## First implementation checkpoint

Consumed reviewed shared dependency #30 at 25f1972 on this branch; #27 is its
ancestor. The shared implementation is unchanged. Its contract is accepted in
#4; private-draft intent/routing remains separate and is not exposed here.

Authenticated POST /v1/sources accepts only title and content plus a UUID
Idempotency-Key. It creates one immutable manual snapshot with server-generated
snapshot key/reference, revision 1, coverage=snapshot and aware retrieval time.
Replay returns the original saved version/time; changed evidence under the same
key returns 409. No source update, inference, responsibility or send is triggered.

GET /v1/sources returns {sources, limit:50}; GET /v1/sources/{uuid} returns the
private current snapshot/content, with identical absent/not-owned 404 responses.
Metadata matches the shared projection. Successful responses are no-store.
The existing verified-session proxy permits only these exact paths/methods and
retains origin, JSON, byte-bound, token-only and no-cache behavior.

Fifteen focused real-Store API cases pass on isolated local Postgres, covering
idempotency/conflict, isolation, spoofed fields, setup/authentication, Unicode byte
bounds and storage failure. Three proxy regressions failed before allowlisting
and pass after. All 59 web tests, TypeScript, Prettier and production build pass.
No new UI is present yet. All 293 backend tests pass against disposable Postgres
in Python UTF-8 mode; Ruff lint/format and diff checks also pass.

Windows finding in the inherited #27 tests: fixture read_text defaults to cp1252,
corrupting the en dash in a source-backed rubric quote; isolated scenario fails
before drafting. Reported to the owner in #27 comment6492656206. No quote gate or
other-owner test was changed. Full suite passes in Python UTF-8 mode.
The uv executable is absent from PATH; the existing .venv Python runs pytest/Ruff.

Live B2 results: not run. No provider call, real academic data or deployment.

## Snapshot interface checkpoint

Academic context is a new view in the existing workspace; Overview remains the
default. It saves, lists and opens private snapshots through the existing API
client and verified proxy. The same form stays mounted across workspace tabs so
unsaved text survives navigation. Text stays in memory only; the interface explains
that refreshing/closing clears unsaved text. Identity changes and expired sessions
clear the private view and ignore late requests. No user ID is sent as authority.

Unconfirmed saves retain the exact immutable payload and UUID for an explicit
check/retry; fields stay locked until resolution. A confirmed conflict or validation
failure allows correction. A completed save clears fields, shows the saved text
and returns keyboard focus after fields become enabled. Source HTML is rendered
as plain text. Delayed detail/list responses cannot replace a newer selection/save.

Eight component cases plus workspace navigation coverage bring the full website
suite to 68 passing tests. TypeScript, Prettier and the production build pass.
The final backend regression run also passes all 293 tests on disposable Postgres
in UTF-8 mode; Ruff lint/format and diff checks pass. No backend code changed in
this UI checkpoint.
Tests first exposed conflict-recovery and post-save focus failures; both pass after
their fixes. The premium static audit reports no findings; this is supplementary
to actual component/browser checks, not proof of runtime behavior by itself.

An ignored standalone browser fixture rendered the actual components and CSS with
fictional sources and all API calls intercepted in memory. Desktop 1440px and phone
390px/320px inspections found no horizontal overflow. Keyboard Tab reached pasted
text; simulated lost response preserved the draft, explicit retry confirmed the
save, and focus returned to the title. Screenshots are local verification evidence,
not live Clerk/account/backend evidence. The temporary preview was stopped.

Private-draft controls/results are not exposed by this checkpoint. A separate
review found PlannerDecision nonblank validation moved off the base class in #34
head3560a9; exact before/after reproduction is recorded in PR comment6509066599.
Wait for the owner fix and exact-head review before consuming that dependency.

## Private results implementation evidence

Added safe responsibility summaries, private bounded artifact lists and private
artifact/latest-check reads through the authenticated API/proxy. Only GET is
allowed for result routes. Actual Store tests cover other-account404, empty duty,
failed then passed reports and source-change staleness with historical checks
preserved. A failing regression also exposed a missing no-store header on storage
errors; the common redacted storage-error response now supplies it.

The existing workspace's Private results view shows saved drafts, disclosure,
citation claims/quotes, policy/rubric evidence and check findings as plain text.
Stale, missing and failed checks cannot be presented as a current passed draft.
Malformed responses remain unavailable; late responses and account/session
changes clear or ignore private state. No artifact readiness or draft permission
is changed by this read-only view. Private-draft authorization remains unwired.

Verification: 86 web tests pass, including new result/proxy cases; TypeScript,
Prettier and production build pass. The snapshot focus assertion now waits for its
post-render effect instead of racing it. All 295 backend tests pass again after
the storage-error no-cache fix, against disposable Postgres in UTF-8 mode. Ruff
lint/format pass. No new shared dependency or migration was consumed.

An ignored standalone fixture rendered actual result components/styles with
fictional in-memory records. Desktop1440 and phone390/320 have no horizontal
overflow; the narrowest navigation uses two columns. Ready and stale presentations,
focus on the loaded review and keyboard expansion of policy evidence were checked.
Screenshots are local offline evidence. Real Clerk/backend result acceptance and
live model quality are not established by this fixture. No live provider call,
send, share, submission or deployment occurred.

## Standalone private-draft decision preparation

Prepared a callback-based consent form without mounting it in the workspace or
adding a transport/API consumer. It requires an objective, one to eight saved
sources and explicit private-draft consent. Editing the objective or selection
invalidates consent. Unconfirmed saves retain the exact frozen payload and retry
key; definite rejection requires fresh consent. Identity/session changes clear
private input and fence late responses. Only a private-draft receipt confirms the
request; confirmation still does not claim policy permission or work completion.

Eight new component cases bring the website suite to 94 passing tests. TypeScript,
Prettier and production build pass. Actual component/CSS browser checks at 1440,
390 and 320px found no horizontal overflow. Keyboard consent, simulated lost
receipt, explicit retry and focus restoration passed with an in-memory callback.
The existing backend checkpoint remains 295 passing tests on disposable Postgres;
this preparation changes no backend code. All evidence is offline.

Claim: coordination comment6509628481. Integration still waits for the owner to
restore base PlannerDecision nonblank validation in #34 and for exact-head review.
This form is unconnected preparation, not an available drafting workflow. No model
or provider call, migration, send, share, submission or deployment occurred.

## Reviewed dependency and authenticated delegation assembly

The owner restored the base planner validator at #34 head db241ab. Independent
exact-archive checks passed all seven planner regressions plus eighteen assessor
cases, Ruff lint/format, and all four exact-head CI checks were green. Integrated
that reviewed dependency into this feature branch; no edits to the owner's branch.

The app now exposes explicit POST responsibilities through the existing verified
session/proxy and atomic create_draft_responsibility boundary. Only objective,
one to eight distinct source IDs and strict true consent are accepted. UUID retry
identity, server-owned budgets, capacity, same-origin mutation and no-store are
preserved. GET responsibilities/{uuid}/status uses the published controlled private
projection; absent/other-account status and sources have matching private errors.
No model, policy, readiness or browser owner override is introduced.

Acceptance tests first failed against the missing API/proxy routes. New actual
Store cases cover atomic save/replay/conflict, analysis-key rejection, private
isolation, paused work remaining unclaimed, consent/type/field bounds, byte limit,
capacity and redacted storage failure. The former read-only collection assertions
now permit only this explicit create route; artifact/status mutations stay closed.
The consent form remains unmounted pending the next owned UI/status integration.

Integrated validation: 352 backend tests pass on disposable Postgres in UTF-8
mode, including the new API cases; all 95 web tests pass. Ruff lint/format,
TypeScript, Prettier, production build and diff checks pass. Migration009 ran only
through test setup on the disposable database. No retained development/production
migration, model/provider call, worker activation, send or deployment occurred.

## Connected student decision and status

Academic context now reuses its loaded private source list in the existing
private-draft consent form. The existing request client sends the explicit
objective/source/consent payload and stable UUID retry key to the authenticated
API. No request is sent by loading, selecting a source or refreshing status.
Confirmed receipts show the controlled work status and a route to Private results.
Selected responsibilities in Private results show the same shared status view.

Manual status refresh uses only the published GET projection. Mismatched IDs,
unknown states/reasons and malformed responses stay unavailable. Source-change,
blocked assessment and blocked workflow states override historical assessed/ready
values; status never grants sharing, sending, submission or instructor approval.
Definite missing-source rejection returns the form to review with fresh consent.
Unknown outcomes keep the immutable original request. Account-keyed workspace
lifetimes and a shared session-expiry boundary clear hidden context/decision data
as well as visible results and abort outstanding requests.

Verification: 107 website tests pass, including ten connected transport/status
cases and a cross-view session-expiry regression observed failing before its fix.
TypeScript, Prettier and production build pass. The real-Store API acceptance test
saves a fictional snapshot, confirms private intent, runs the existing worker with
scripted assessments, then reads the ready draft/citations/disclosure/checks and
proves second-account denial with no outbound message. Full backend suite passes
353 tests on disposable Postgres. These scripted results do not prove real model
quality, Clerk/browser/backend acceptance or actual WhatsApp delivery.

An ignored fixture rendered actual context/results components and request client
with only fictional in-memory responses. Browser checks at1440/390/320px found no
horizontal overflow and exercised keyboard consent, lost receipt/exact retry,
pending/ready status, private result navigation and focus on the loaded review.
No retained development/production database migration or worker/provider activation
was performed. M1 and live M2 remain incomplete.

Fresh code review found two recovery defects, both reproduced before fixes:
definite capacity429 now unlocks the form for review and fresh consent; a
source_changed status now invalidates the open cached ready presentation and draft
list, retaining passed reports only as historical evidence. Focused regressions
and the full107-test web suite pass after the fixes; browser recheck confirms the
ready-to-stale transition. No runtime/shared behavior was changed for either fix.

## Saved deterministic format findings

Reviewed and integrated #38 exact fab095f:43 independent format/assessor/planner
tests pass and four exact-head CI checks succeed. This dependency adds narrowly
supported source-backed word ranges and separate-disclosure rules; it does not
claim general natural-language enforcement or live model quality.

Private results now explains all seven delivered format failures and optionally
shows the saved whitespace-word count, quoted inclusive ranges/source versions,
disclosure-check mode and parser limits. Old reports without this evidence remain
readable. Evidence is validated before display; invalid IDs/bounds/types and nested
format errors contradicting the overall report cannot appear ready. Range display
is bounded to the first30 with an explicit total. Wording makes disclosure
conditional on policy rather than inferring permission from a saved format mode.

Six new viewer regressions bring the website suite to113 passing tests. The fresh
review's two findings (unconditional disclosure wording and contradictory nested
failure/readiness) both failed before correction and pass afterward. All376
integrated backend tests pass on disposable Postgres; Ruff lint/format, TypeScript,
Prettier, production build and diff checks pass. Actual-component synthetic browser
checks verify keyboard expansion and desktop/320px no overflow. No live provider,
retained migration, worker activation, sharing, send, submission or deployment.
