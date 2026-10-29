# B2 — private academic snapshots

Owner: Murtazo. Branch: codex/b2-snapshot-intake, from reviewed 6accd71.
Coordination: #4 comments 6491647927 and 6491917360. Akbar approved the B2/A3
workflow while M1 provider setup is deferred. M1 remains incomplete. This work
order records the agreed direction; shared implementation is not yet delivered.

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
web/components/workspace.tsx, this work order and web/README.md.
Akbar retains shared storage/runtime/contracts and #26/#27 internal validation.
No shared implementation, migrations or STATUS.md edits are claimed here.

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
Current implementation/test/live results: not run for B2; design preparation only.
