# Contracts — implemented boundaries and historical increments

> Revision7 planning note (October 30): this file describes implemented contracts
> and their historical increments. New C1–C7 interfaces in
> [WORK-ORDERS.md](docs/WORK-ORDERS.md#shared-interface-checklist-proposed-not-executable-yet)
> are proposals until both owners agree a version. No sync endpoint, supervisor
> action, freshness relaxation or proactive send permission exists merely because
> the plan names it. Existing private-draft and policy gates remain effective.

## Agreed connection and sync design; implementation pending

[C1/C2 v1 proposal](docs/contracts/CONNECTION-SYNC-v1.md) (#47) defines pairing,
connection identity, sync receipts/coverage and last_checked semantics. M agreed exact
ccf84dc in [review6537274371](https://github.com/Akbarhoja/wrytely-agent/pull/48#issuecomment-6537274371).
This is design agreement, not implemented routes/store methods or relaxed permission gates.
[C3–C7 v1 proposal](docs/contracts/AGENT-ACTIONS-v1.md) adds retrieval, student
decisions, typed delivery, private files and operational accounting for the same
owner review. C3–C7 remain proposed; C1/C2 implementation proceeds in P1-A1 slices.

## P1-A1 first slice — Canvas pairing and credential lifecycle (#58)

Implemented in shared/source_connections.py, composed into Store with additive migration010.
No HTTP route, extension pairing UI, sync ingestion or Outlook secret storage is added.
C1/C2 design agreement remains separate from review of this implementation.

`Store(url, *, canvas_origins=())` takes an operator-owned tuple of exact HTTPS origins.
Default is empty: pairing and credential use are disabled until M's assembly explicitly
supplies approved configuration. Reject paths, ports, query/fragment, userinfo, non-ASCII
and noncanonical origins; no URL fetch occurs. This is not a browser-posted allowlist.
Existing Store callers are unchanged. Origin consent/actual Canvas access remain separate.

Operator configuration slice #61: `Settings.canvas_origins` reads
`AGENT_CANVAS_ORIGINS` as a JSON list, for example
`["https://canvas.example.edu"]`. Default/explicit empty list becomes `()`.
At most20 distinct exact origins; malformed JSON, null, scalar/object values,
duplicates and invalid origins fail validation rather than being trimmed or guessed.
The same canvas_origin function validates Settings and Store. M passes the validated
tuple to Store in owned app assembly; this configuration field alone does not wire
routes, grant school access, prove readiness or modify a deployed environment.

- `create_pairing(verified_user, allowed_origin)` requires a provisioned verified user
  and configured origin. Returns `{challenge, code, expires_at}`. challenge and code are
  the same192-bit copyable one-use secret, expires_at an aware ISO timestamp10 minutes
  ahead. Persist only SHA256. A new code replaces the previous unconsumed code. Maximum
  five issuances per account per10-minute window persists across redemption. Never log
  this return value, expose it to another account or put it into model/conversation data.
- `redeem_pairing(code, device_public_id)` atomically consumes a valid code and creates
  a pending_identity connection. Device ID is1–128 ASCII letters/digits/dot/underscore/
  colon/hyphen, not student authority. Return safe status below plus ingestion_bearer,
  a256-bit random bearer shown once, stored only as SHA256, default expiry30 days.
  Re-pairing the same owner/origin/device preserves connection_id, increments generation,
  clears prior subject and replaces the credential. Different devices are distinct.
  Issuance is not a successful device connection until this transaction commits.
  If a successful redemption response is lost, the server cannot recover its hash-only
  bearer: request a fresh pairing code and re-pair, fencing the lost credential.
- `bind_canvas_identity(credential, origin, provider_subject)` validates live credential
  under an agent lock and binds one nonblank bounded provider subject. M must obtain/check
  it in the same-session adapter, not a browser account-ID input. Same subject rebind is
  idempotent; changed subject commits generation increment, credential revocation and
  reconnect_required before raising SourceCredentialRejected. No relabeling old evidence.
- `source_connection(verified_user, connection_id)` returns None for missing/nonowned/
  malformed IDs. Otherwise only connection_id, provider, origin, state, generation and
  credential_expires_at. UUID/timestamp are strings; no subject/device, digest or secret.
  Expired pending/connected credentials project reconnect_required, without writing on read.
- `rotate_or_revoke(verified_user, connection_id)` implements revoke, not an unconfirmed
  credential replacement. Owner lock scopes update, increments generation, clears digest,
  marks disconnected and invalidates that account's outstanding pairing challenge.
  Fresh authenticated pairing is required to reconnect. Nonowned/missing/malformed IDs
  raise the same LookupError("Not found"). Revoke/re-pair and bind use the same agent lock.

Internal `_lock_canvas_credential` authenticates/fences in an existing transaction;
it is not an exposed method or independent grant to sync. Future sync must additionally
check connected state, subject, selected scope and exact generation in that transaction.
There are no scan rows in010 to abort yet. Source keys must retain subject/generation
provenance when a device is re-paired; old evidence must not become a new login's data.

Redemption budgets persist for schema-valid attempts, including wrong/expired/used
codes: at most120 per server per minute and10 per claimed device per minute.
Malformed code/device syntax is rejected before the database budget, so these are
not limits on every HTTP request; M must bound and rate-limit the public route. Global limit is checked
before inserting device buckets, with one transaction lock and expired-bucket cleanup.
Device identity alone is untrusted and cannot bypass the global cap. The cap is an
initial deployment-wide pairing throttle, not protection against service denial or
an IP/authenticated-user HTTP rate limit. M must review its capacity and assembly rate
limits before public rollout; no rate row stores the actual device ID or code.
PairingLimited maps to429; PairingRejected has one generic invalid/expired/used-code
message; SourceCredentialRejected maps to generic401/reconnect. Storage exceptions
propagate and roll back credential/challenge changes, never empty successful responses.
No mutation or data from these secrets is sent to providers/models. Private/no-cache
HTTP assembly and extension-private secret storage remain M-owned and unimplemented.

Migration010 only adds three Canvas lifecycle tables in wrytely_agent, replayed by the
existing checksum ledger. Applied historical migrations remain unchanged;008 stays
parked. Test only against a disposable database here. Roll out010 explicitly before
assembling these methods; rollback application consumers first and retain additive data
for review, rather than automatically deleting credentials/history. No Railway database
or existing Wrytely production migration is authorized by publishing this code.

## P1-A1 next slice — Canvas context, selection and discovery sync (#58)

Implemented in shared/canvas_sync.py, contracts/canvas_sync.py and additive migration011;
composed into the existing Store. M agreed scope/bearer direction and requested context
in [6537874178](https://github.com/Akbarhoja/wrytely-agent/issues/58#issuecomment-6537874178).
A confirmed the exact context in6538966628 and list in6539057716; implementation still
requires counterpart review before HTTP consumers. This is metadata discovery storage,
not academic source ingestion, a public sync route or completed P1-A1.

`canvas_connection_context(credential, origin)` checks the current ingestion bearer,
configured exact origin and credential expiry under the existing agent lock. Returns
unchanged safe C1 projection plus scope_revision, mode, course_ids, resource_kinds and
`discovery: {coverage,last_attempt_at,last_complete_at}`. Initial scope_revision=0,
mode=explicit_set, both lists empty, coverage=unknown and timestamps=null. Pending
identity can read that safe context but cannot begin sync. Connected empty selection
permits metadata discovery only. No subject/device/hash/bearer/opaque cursor is projected.
Dates are ISO strings. last_complete_at is terminal receipt time, not an academic source
freshness grant; captured observation times stay in catalog rows. P1 freshness consumers
and source check records are not implemented here.

`list_source_connections(verified_user, *, limit=20, cursor=None)` returns
`{connections:[safe C1 projections],next_cursor}`. Strict integer1–20; immutable
created_at/id descending. Opaque cursor is last returned connection UUID, looked up
under the current verified account on each request. Malformed/absent/other-account
cursor raises the same LookupError("Not found"). It grants no authority and contains
no embedded user data/signature. Empty/unprovisioned list is empty. No total count,
provider subject/device or credentials. New rows require restarting pagination to see.

`set_canvas_scope(verified_user, connection_id, generation, *, mode, course_ids,
resource_kinds)` requires current connected owned generation and nonexpired credential.
Modes explicit_set/all_active. Up to1000 distinct numeric-string course IDs from the
current generation's observed catalog; missing_pending_confirmation entries cannot be
newly selected. all_active takes course_ids=[] and derives known active courses only,
not unknown/missing courses from a partial catalog. Kinds: syllabus, assignments,
announcements, discussions, modules, pages, files, submissions, grades. Return context.
Duplicate IDs/kinds, arbitrary IDs and unsupported kinds reject. Identical normalized
selection returns existing scope; changed selection advances scope_revision/generation,
retains the live bearer and carries same-subject catalog provenance forward. Old scans
abort with scope_changed. Device obtains current generation through context without a
Clerk session or re-pair. Re-pair/account switch/revoke instead clear scope/catalog view,
advance revision and abort active scans. Old evidence remains private historical data.

### Discovery scan methods and limits

The C2 begin/resume/commit/finish signatures in CONNECTION-SYNC-v1.md are implemented
for discovery metadata. actor is the ingestion bearer, resolved inside the transaction;
no posted owner ID. Each operation checks connected state, current generation/scope and
subject where supplied before reading a receipt. One active scan/connection,300-second
replaceable writer lease,24-hour lifetime, monotonically increasing scan_sequence.
Begin replay returns its ORIGINAL saved lease/checkpoint, not a later writer's token.
Resume key replays its original response; a new resume key replaces the writer lease
and returns the latest durable checkpoint. Resume does not refresh observations.

Checkpoint exactly `{resource:"courses",next_cursor,sequence,scope_revision}`; strict
integers, bounded private cursor, sequence0 initially. commit_sync_batch accepts only
schema_version integer1 and resource `{course_id:null,kind:"courses"}` in this slice.
At most50 items/page,100 pages/scan,5000 cumulative records,1MiB serialized envelope,
4000-character opaque cursor; replay keys1–128 ASCII letters/digits/dot/underscore/
colon/hyphen. Client network body limits remain M's responsibility. Cursor stays opaque
and private, never fetched here. More-pages cursor must accompany partial/more_pages;
repeated current cursor rejects. Cumulative seen_count must match. No duplicate course
IDs in a page or across pages. Captures require strict aware RFC3339, within scan start
and at most five minutes ahead of server time. Historical pre-scan uploads are rejected
in this increment; no historical-source ingestion is claimed.

Each course item has provider_id (positive numeric string), provider_updated_at (nullable
metadata), title<=500, exact origin/courses/ID reference, content="", fields exactly
course_code/timezone/enrollment_state (bounded nullable strings), coverage and missing.
Full syllabus/assignment text cannot be smuggled into discovery. Server computes C2
content digests; course metadata does not create academic source_versions, so batch
receipt source_versions is []. Receipt/checkpoint/catalog update atomically; storage
failure rolls back all of them. Same batch key + canonical body/checkpoint replays its
original receipt even after lease replacement/expiry, with replayed=true and no cursor,
observation or completion-time advance. Changed payload/key reuse conflicts. An unseen
batch needs the current live lease/checkpoint; retry the same capture after resume.

finish_resource takes key "courses" or a selected course/kind key from the scan's
resource ledger. Complete courses requires an observed final complete page (including
an explicitly observed empty page). Partial/restricted/unsupported terminal receipts
can close a failed enumeration without pretending completeness. No academic resource
can be completed here: only controlled failure/unsupported receipts, or leave it open
for a later implemented collector. Complete course discovery is independent of those
resources. finish_sync requires every resource terminal; aggregate is partial if any
required resource is not complete. It cannot imply academic collection from metadata.
all_active newly observed active courses acquire required resource rows; they cannot
silently disappear from the scan's completeness requirements.

Only complete enumeration marks previously known absent courses
missing_pending_confirmation; partial/restricted/expired scans do not delete or mark
absence. Prior metadata is retained. Reappearance clears pending absence. Active-course
selection excludes pending entries. No confirmed deletion is implemented here. A prior
complete timestamp is retained on failure and never advanced by receipt replay. Terminal
resources reject new writes/different outcomes; exact finish-key replays are allowed.

Hard scan expiry is enforced on every operation. Expiry/aborted-resource history is
persisted when authenticated context/new begin performs cleanup; a rejected transaction
rolls back its attempted cleanup but still rejects expired writes. Context never grants
freshness from that cleanup. No continuous cleanup worker is deployed. Revoke/scope
changes abort scans in the same transaction that fences credentials/generation.

Controlled CanvasSyncConflict.code includes identity_required, generation_changed,
scope_changed, subject_changed, replay_conflict, resume_existing_scan, checkpoint_changed,
lease_expired/replaced, scan_terminal, resource_terminal, resource_not_selected,
incomplete_resource, resources_open and pagination/cursor/selection limits. HTTP mapping
is M-owned:409 for state conflicts, generic401 for SourceCredentialRejected,422 for
invalid envelope/selection, private404 for missing owned connection. Never log raw
validation input, bearer, checkpoint/cursor or provider data. No runtime task, model call,
source content event, email actor/secret or external action is introduced here.

Migration011 adds metadata/receipt/catalog/resource tables and scope columns, tested only
on disposable Postgres. Apply explicitly after010 before any new consumer deployment;
do not modify applied SQL. Existing production/dev ledger remains001–007+009 until
separately authorized. Roll back consumers first and preserve additive history for review.
Remaining P1-A1: academic version/check/event transactions and segmentation, shared
freshness consumption, Outlook credential/actor lifecycle, then assembled/live checks.

## Deterministic draft format checks — issue #37

verify_artifact now checks supported formatting before semantic review and stores
optional deterministic_checks in its existing report: errors, word_count,
disclosure_placement, word_ranges and limits. No mandatory API/model field or
schema changes. Report consumers may ignore this additive evidence; new error
strings must remain visible through their generic finding fallback.

Word count is len(body.split()): whitespace-delimited tokens; a hyphenated token
or number counts once. Title, citations and separate disclosure are excluded.
If default policy requires disclosure inside body, those body tokens are counted.
Supported numeric rubric syntax is an exact quoted instruction beginning
“Write [a] N–M word[s]”, optionally with a hyphen before word; hyphen/en dash/em
dash ranges are recognized case-insensitively. Each bound is 1–10,000, inclusive.
All recognized whole-draft ranges apply; incompatible ranges report
word_count_bounds_conflict. Too-short/long reports word_count_out_of_range.
Numeric word requirements not parsed by this narrow syntax report
word_count_requirement_unparsed; invalid bounds report word_count_requirement_invalid.
No unsupported numeric limit is silently called deterministically verified.
This does not interpret section-specific counts or all natural language. Only
supplied exact rubric quotes are scanned; completeness of extraction still needs
semantic review. Unsupported constraints require clarified source evidence.

Disclosure-required policy retains the existing body-and-field gate by default.
Only the cited policy source's explicit standalone line
“Include this disclosure separately from the word-counted body:” followed by a
nonempty required text line selects separate_field. The disclosure must equal
that exact line and be absent from body. Missing/different text reports
disclosure_text_mismatch; duplicate body insertion reports disclosure_must_be_separate;
conflicting instructions report disclosure_format_ambiguous. This honors the
existing M2 assignment, not a new permission policy. No researcher/group source
may relax placement unless it is the cited policy source; evidence/provenance
checks remain mandatory. Other wording retains the existing conservative body
gate and requires review. Generation prompts request matching placement; semantic
review still assesses actual disclosure/policy adequacy.

Format failures persist needs_revision and reach bounded revision feedback before
a separate semantic call; a model cannot override failed deterministic checks.
Review drafts remain privately inspectable. This does not grant consent, final
readiness on its own, sharing, submission or sending. Default policy tests remain
unchanged; the M2 fixture now correctly uses its required separate disclosure.

## Explicit private-draft intent and routing — issue #33

Agreement: coordination #4 comment6492493685. Migration 009 adds
private_draft_intents; 008/A4 stays excluded. No deployment/migration execution
is implied. Apply 009 on an isolated environment before running this worker code.

`create_draft_responsibility(verified_user_id, objective, key, *, source_ids,
max_steps=6, pending_limit=20, max_revisions=2)` reuses atomic bound setup and
returns the same native responsibility row. The authenticated app calls it only
after explicit student confirmation: prepare one private draft, with no sharing,
submission or sending. Pasted instructions are evidence, not that confirmation.
Budgets are server-owned; max_revisions is an integer 0–2. Source limits/ownership,
rollback and idempotency match create_bound_responsibility. Intent's original
memory revision and revision budget persist in the same transaction as bindings
and the initial plan. Original request metadata includes private_draft mode and
revision budget. Changing either conflicts; an analysis-only key cannot upgrade,
and a draft key cannot downgrade. The old analysis-only method is unchanged.

At a planning episode with intent, the runtime assesses current owned bound
evidence using assess_draft_requirements, then commits the result through a
lease/pause/current-revision fence. Evidence quotes and freshness are revalidated
in storage. A missing/nonpermitting policy or missing rubric blocks the draft duty
and its task with draft_policy_or_rubric_blocked. Saved assessment is reused across
attempts and planner episodes. It remains a fallible interpretation of sources,
not a truth guarantee; the existing separate drafting preflight and mandatory
artifact verification remain required. Provider failures use bounded normal retry.

Only a duty with intent receives DraftPlannerDecision's extra action=draft. work
remains ordinary analysis; draft creates one academic task and attaches its
immutable policy/rubric/revision specification atomically before commit/claim.
Stored intent, current evidence, step budget and duplicate checks constrain this
choice. A consumed intent cannot spawn another drafting workflow under a new key.
done before an actually completed, ready artifact is blocked as private_draft_not_ready.
No model can grant its own consent or readiness. Model/source instructions cannot
enable drafting on an analysis-only duty. Draft generation/checkpoint/revision
continues through the existing worker path. No app polling upgrades are needed.

Source changes revoke old task leases through existing memory invalidation;
intent's original revision cannot be reused for new evidence. Pause fences both
assessment commit and subsequent work. No A4 automatic reauthorization is added.
Crash before a result is persisted may repeat model usage; saved assessment and
drafting checkpoints avoid repeating already committed progress. This is not
exactly-once model billing or an unbounded agent loop.

`draft_responsibility_status(verified_user_id, responsibility_id)` is the exact
private app read. None means absent/not-owned, mapped to the same private 404.
Storage errors propagate. One SQL snapshot returns JSON-safe fields:

| Field             | Values / meaning                                                                                                                                                                               |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| responsibility_id | UUID string                                                                                                                                                                                    |
| requested_mode    | analysis or private_draft                                                                                                                                                                      |
| status            | active, blocked or done; revision mismatch reports blocked                                                                                                                                     |
| reason            | null, source_changed, draft_policy_or_rubric_blocked or draft_work_blocked; never raw model prose                                                                                              |
| assessment_state  | not_requested for analysis; pending, assessed or blocked for draft intent                                                                                                                      |
| workflow_state    | not_requested for analysis; pending before attachment; queued/running after attachment; ready_for_review only for a completed task with a ready artifact; blocked on failure or stale revision |
| artifact_id       | latest saved draft UUID string or null; may reference an unready/stale review artifact                                                                                                         |

Assessment state is historical and can remain assessed after source change;
status/reason/workflow and artifact stale flags take precedence. requested_mode
does not mean policy permits drafting, and ready_for_review never means shared,
sent, submitted or approved by an instructor. Use artifact_review to inspect
private draft/check details; do not hide unready drafts or present stale ones as
current. Existing no-cache/private ownership rules apply. Store.draft_intent,
draft_intent_sources and commit_draft_assessment are fenced internal runtime
methods, not API/model tools. Do not accept browser CoursePolicy, task IDs or
assessment/verifier output as authority. The app/UI consumer remains Murtazo-owned.

The first new planner episode may use two model turns (assessment plus planning);
subsequent planning reuses assessment, and drafting uses its existing bounded
preflight/generation/check/revision limits. Account/global usage gates and live
quality evaluation remain separate; this change makes no live budget expansion.

## Draft requirement assessment — issue #31 (internal helper)

`runtime.draft_requirements.assess_draft_requirements(model, sources)` accepts
1–8 distinct current owned bound source-version records, supplied by trusted
runtime storage (the existing drafting_sources shape: id, content, retrieved_at,
coverage). It does not accept browser-supplied evidence as authoritative. Each
content is nonblank and at most 24,000 characters; timestamps are aware, no older
than 24 hours and no more than five minutes in the future. Invalid/oversized/stale
input fails before inference rather than silently truncating policy evidence.

One structured existing ModelClient call extracts a candidate nullable CoursePolicy,
0–30 RubricItems and a bounded reason. Exact nonblank policy/rubric quotes must
occur in their cited supplied version; malformed output or unbound/invented evidence
raises ValueError. Only a permitting/disclosure-required policy with a nonempty
rubric returns state=assessed; otherwise state=blocked. JSON-safe output includes
policy, rubric, reason, input_tokens, output_tokens, limits and always
authorizes_drafting=false. Sources' freshness is checked again after inference.

This helper has no database/task/action side effects and is not connected to the
worker yet. It does not persist authorization, classify user consent, guarantee
policy interpretation/rubric completeness or make a draft ready. Semantic results
are fallible even with exact quote validation; source injection resistance needs
live evaluation, not a scripted verdict. Provider exceptions propagate to the
runtime's normal bounded/redacted failure path. Before persisting/using results,
the caller must recheck lease, pause and source/memory revision through existing
fenced Store boundaries, persist reusable checkpoints, require explicit student
draft delegation, and retain existing drafting preflight and verification.

The app-facing explicit-delegation and atomic planner-routing proposal is posted
in coordination #4 comment6492266670; consumer agreement is pending. Existing
B2 create_bound_responsibility remains analysis-only. This internal helper does
not expand the agreed B2 API or authorize its app consumer to bypass that gate.

## B2 atomic setup and private reads — issue #29

Agreed in coordination #4 comment 6491917360. Implemented in
shared/bound_responsibilities.py and shared/academic_reads.py, composed into the
existing Store. No migration, endpoint, connector or full-draft authority is added.
App consumers derive user_id exclusively from a verified session. These methods
do not authorize sharing, submission, automatic assignment drafting or inference
from account creation. Existing create_responsibility remains unchanged.

`create_bound_responsibility(user_id, objective, key, *, source_ids,
max_steps=6, pending_limit=20)` returns the existing responsibility row (native
database UUID/datetime fields, as with create_responsibility). Source IDs may be
UUID objects or UUID strings, in a list/tuple of 1–8 distinct IDs. Objective is
trimmed and bounded 1–12,000 characters; key is 1–128; integer max_steps is 1–12;
integer pending_limit is 1–1,000. One transaction locks the user's agent, verifies
every owned source has a current version, creates the duty/bindings with initial
memory_revision equal to source count, then queues one plan at that revision.
Agent locking serializes with source observation/binding and worker claims.
Partial setup is not claimable; failures roll back duty, bindings, messages and
tasks. Paused accounts may save work but workers cannot claim it.

An internal attempt-0 bound_responsibility_setup event retains the canonical
original source set/objective/step budget. Reordered identical requests return the
same duty before capacity checks, without resetting progress or rebinding after
later source updates. Changed payload, or reuse of a legacy unbound request key,
raises RequestConflict. Missing, invalid UUID or other-user source IDs raise the
same LookupError("Source not found"); invalid count/duplicates/bounds raise
ValueError, exhausted pending capacity raises QueueFull, unprovisioned users raise
LookupError("Complete setup first"). Apps validate UUID syntax and map source
absence/not-owned identically. Storage failures propagate; never report them as
empty successful reads. This creates an analysis-only duty, not a drafting request.

Private reads return JSON-compatible dictionaries/lists: UUIDs are strings and
aware timestamps are ISO 8601. Source coverage is the recorded evidence type;
snapshots do not imply live monitoring. All lists have a hard limit of 50 and no
cursor yet; consumers must explain this limit. Lists are stably ordered:

- `source_snapshots(user_id)` returns current source summaries, ordered by
  retrieved_at descending, source_id descending. Empty/unprovisioned account: [].
  Fields: source_id, version_id, title, reference, coverage, retrieved_at,
  external_revision. Historical versions are excluded.
- `source_snapshot(user_id, source_id)` returns that summary plus full stored
  content (bounded by SourceObservation's 24,000-character limit), or None for
  absent/not-owned. Source body is untrusted evidence, not authority.
- `responsibility_artifacts(user_id, responsibility_id)` returns None for
  absent/not-owned duty; otherwise a list (possibly empty), ordered created_at
  descending, artifact id descending. Fields: id, task_id, title, state, stale,
  created_at. Ownership and list retrieval share a repeatable-read snapshot.
- `artifact_review(user_id, artifact_id)` returns None for absent/not-owned;
  otherwise {artifact, latest_check}. artifact fields: id, responsibility_id,
  task_id, memory_revision, draft, state, created_at, stale. draft is the existing
  DraftArtifact payload. latest_check is null before any completed check or the
  latest stored verification report (ordered created_at descending, check id
  descending); it includes passed/errors, assessment, policy/rubric evidence,
  token usage and limits. No raw model histories, lease tokens, agent/user IDs,
  operator credentials or internal request keys are projected. One SQL statement
  reads artifact state, current memory revision and latest report coherently.

stale is independent of historical readiness/check success; it means the bound
responsibility's source memory revision changed. Neither ready nor passed grants
external-action authority. API assembly must retain no-cache responses and private
404 semantics. Do not expose internal readiness commits or accept browser-supplied
CoursePolicy/verification results. Trusted responsibility-level draft intent and
atomic pre-claim routing remain the next separately specified runtime increment;
the app must label this first delegation path as analysis only.

Status: implemented and locally tested; live provider validation remains pending.
Boundary types: `contracts/models.py`. Database: `contracts/001_foundation.sql`.
All private operations use the verified Clerk `sub` as `user_id`.

## HTTP

Base URL: deployment configuration, not hardcoded. Bearer authentication only.
Browser obtains a short-lived session token from existing Clerk authentication and
sends `Authorization: Bearer <token>`. `__session` cookies and user-ID headers are
not accepted by this backend. CORS origins and JWT authorized parties must be
configured for the actual frontend. No credentials go into browser storage code
or source control.

| Method/path            | Input                             | Output / semantics                                                                                                                                                     |
| ---------------------- | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET /healthz           | none                              | Process liveness only                                                                                                                                                  |
| GET /readyz            | none                              | Configuration flags; never a claim that live services were tested                                                                                                      |
| POST /v1/bootstrap     | authenticated, no body            | Existing or newly provisioned agent for this user                                                                                                                      |
| GET /v1/me             | authenticated                     | Agent ID, own user ID, paused flag; 404 before bootstrap                                                                                                               |
| POST /v1/messages      | `{content}` and `Idempotency-Key` | 202 `{task_id,status}`; durable queueing, not a completed answer                                                                                                       |
| GET /v1/messages       | authenticated                     | Own recent messages in chronological order, at most 100                                                                                                                |
| GET /v1/tasks/{id}     | authenticated                     | Own task state; 404 also for another user's task                                                                                                                       |
| GET /v1/tasks          | authenticated                     | `{tasks}`: own latest 50 tasks, newest first; includes status, attempts, controlled error, creation time and a title clipped to 180 characters from the source message |
| POST /v1/agent/control | `{paused: true/false}`            | Own agent state                                                                                                                                                        |

Repeat a message request with the same key and identical content to safely retrieve
the original task. Reusing its key for different content returns 409. Missing key
or invalid body returns 422. Pending-work limit returns 429. Unauthenticated or
invalid sessions return 401. Unconfigured storage returns 503.

## Background execution

`TaskLease` identifies task, agent, user and owning attempt. Only a live lease can
write events or complete. `ModelClient.turn(history, tools)` returns typed model
output and usage. Meta's Responses API is the production adapter. Test models are
only injected in tests; no runtime fake-model mode exists.

The current tool is `get_academic_context` with exactly `{}` arguments. Scope is
server-controlled. Initial context is the current message, not a synchronized
semester model. Full planner, handoff resumption and course ingestion are later
work, not hidden assumptions in the foundation contract.

## Messaging adapter boundary for B1b

`ChannelAdapter.send(recipient, text, action_id)` returns `DeliveryResult` with a
durable internal ID and accurate provider evidence. The current API does not yet
call an adapter. Discuss durable delivery tables, verified account linking,
webhook signatures and ambiguous outcomes with the lead before implementing B1b.
No phone/chat identifier is trusted as a Clerk identity without verified linking.

## Contract changes

Propose a small PR with new types, documented behavior and tests. No duplicate
database client or parallel auth mechanism. Do not alter migration 001 after it
has been deployed; add a versioned migration instead. Both engineers may inspect
all implementation code to diagnose problems.

## B1b adapter preparation — October 28

`integrations/whatsapp.py` implements raw-body HMAC signature verification, configured
business/phone filtering and text extraction, plus a single-attempt Cloud API text
sender. HTTP clients must have transport retries disabled. Provider acceptance is
not recipient delivery; timeouts, server failures and malformed successes remain
`unknown`. The action ID refers to our ledger, not provider deduplication.

These functions are not exposed as HTTP routes or called by the worker yet.
Before enabling them: persist webhook IDs uniquely, verify account/number linking,
add durable outbound intents and permission checks, enforce the conversation
window, implement approved templates and consume status callbacks. Never route a
phone number directly to a Clerk user ID. Media intake remains future work.

## B1b durable inbound path

Migration 002 adds link challenges, verified numbers, inbound IDs and a reply
outbox. Migration runner now applies ordered versioned migrations with checksum
validation; 001 is unchanged.

- `POST /v1/whatsapp/link`: Clerk-authenticated; bootstrapped accounts receive one
  single-use challenge, valid ten minutes. Reissue invalidates its predecessor.
- `POST /v1/whatsapp/unlink`: Clerk-authenticated; unlink own number, revoke pending
  challenge and cancel own queued/deferred outbound messages.
- `GET /webhooks/whatsapp`: configured token challenge verification.
- `POST /webhooks/whatsapp`: bounded raw body, app-secret signature, configured
  business and phone filtering. Persist accepted text and task atomically; unique
  provider ID prevents duplicate tasks. Unknown senders are ignored. Return 503
  when work cannot be durably accepted because of queue capacity or storage.

Worker completion for an inbound WhatsApp task atomically creates its queued reply
if the original link is still current. Web tasks do not create WhatsApp replies.
Delivery worker, status callback ingestion, template/window rules and web linking
controls are still pending. No automatic WhatsApp sends are enabled.

## A1 episode resumption

`Store.episode_history(lease)` verifies the current live lease and returns only
that task's committed model turns and tool outputs across attempts. The runtime
reconstructs the model history in event order, retains encrypted reasoning blocks,
executes pending read-only calls, and reuses a saved final response. A model turn
now records `text` as well as its full output and usage. Legacy turns without text
cannot recover their final text through this new field and may require inference.

Each episode remains bounded and total attempts remain capped. Source mutations,
new responsibilities and true next-task selection are separate future stages.
Do not add a side-effect tool to replay without an action ledger and documented
reconciliation behavior. A crash after an external action but before its checkpoint
can otherwise duplicate that action. Current tools are read-only.

## A2 responsibility planner — internal integration contract

Migration 003 adds responsibilities and typed plan/academic tasks. Trusted callers
use `Store.create_responsibility(verified_user_id, objective, request_key,
max_steps=6, pending_limit=20)` only after explicit delegation. The caller must
supply a verified session identity; do not accept user IDs generated by a model or
read from an arbitrary request body. No new HTTP endpoint or web UI is added here.
`Store.responsibilities(user_id)` returns the account's latest 50 duties.

Creation is idempotent for the same objective/key/budget and atomically queues one
planning task. Changed payload under the same key conflicts. Missing agent fails;
existing pending-work capacity is respected. Steps are internal analysis only,
not externally authorized actions or verified assignment artifacts.

The worker requests one typed `record_plan` decision from the configured model.
Choices are work, blocked or done. A saved decision survives a new worker attempt.
Applying it atomically completes the planner task and creates at most one academic
step. Finishing that step saves its result and queues the next planner atomically.
The planner sees the objective and up to 12 step records (result excerpts limited
to 4,000 characters). Model calls and attempts retain existing bounds.

A repeated step key, empty work instruction or exhausted step budget blocks the
duty. Step budget defaults to six, hard maximum twelve. Different names for
semantically repetitive work are not deterministically detected; the model is
instructed to avoid them and the hard budget bounds this failure. Failed tasks
block their responsibility after attempt exhaustion. Blocked work occupies no
worker slot. Pause prevents new claims; active tool/result writes recheck pause.

Internal task prompts use role `internal`, and internal results are excluded from
the ordinary conversation list. They must not be presented as student messages.
`done` here means internal analysis completed according to the planner; it is not
independent verification, grading, delivery, or submission. Initial done without
any work is blocked. Source/version change handling, commitment extraction,
verified artifacts, student decision requests and blocked-duty resumption are
future stages. This loop does not yet activate through ordinary chat messages.

## A2 academic memory — draft internal contract (issue #6)

Connector handoff is proposed in coordination issue #4, not yet agreed or wired.
No new HTTP endpoints, adapters or frontend controls are part of this change.
Trusted assembly must derive user identity from the verified session/connection;
a source body or model may never provide the authority to access another account.

`SourceObservation` contains source_key (stable connector/item key), external_revision,
title, reference, coverage (`snapshot`, `api`, `feed`, `group`), content and a
mandatory timezone-aware retrieved_at. Text is limited to 24,000 characters.
References are stored as evidence only; the memory layer does not fetch URLs.
Adapters must not pass credentials in content or references.

`Store.observe_source(user_id, observation)` stores immutable version evidence and
returns its ID and source_id. Repeated key/revision with identical evidence returns
the original version and original retrieval time; it does not manufacture a fresh
sync. Changed evidence under the same revision raises RequestConflict. Distinct
versions with equal retrieval time conflict. A late observation is preserved but
cannot displace a version with a newer retrieval timestamp. This orders recorded
observations, not arbitrary vendor revision strings. Adapters must reconcile vendor
ordering where necessary. Retrieval timestamps over five minutes in the future
are rejected. Unprovisioned identities fail.

`Store.bind_source(user_id, responsibility_id, source_id)` explicitly attaches one
owned source to one owned duty, idempotently; max eight sources per responsibility.
Before the initial plan starts, binding enriches its memory revision atomically.
Once work starts, adding a source blocks old work as source_changed. No cross-user
or unbound source is exposed to the planner.

`Store.record_source_fact(lease, version_id, claim, quote)` is a fenced internal
storage boundary, not a model tool or a public route in this stage. It requires a
current source version bound to this responsibility and an exact substring quote.
Identical fact retries deduplicate by a SHA-256 digest of claim/quote. Claim and
quote limits are 2,000 characters each. Exact quote validation establishes text
presence only, not that the quote supports the claim. A3 must implement that check.

The planner/context now receives academic_memory: up to eight source excerpts
(6,000 characters each, with truncation flags), version IDs/revisions, references,
coverage and retrieval timestamps; up to 50 recent facts with current-version flags.
A fixed 24-hour heuristic flags freshness review; it is not a provider freshness SLA
or proof that a portal was checked. Snapshot input does not monitor later changes.

Promoting a newly observed version increments attached duties' memory revision,
blocks queued/running tasks, revokes their leases and blocks each affected duty
with source_changed. Past facts/results remain for audit; old facts are flagged
noncurrent and old step results stale. Task commits also check the responsibility
revision. A stale saved model/planning turn cannot complete or spawn fresh work.
This stage stops stale work; automatic revision/resumption belongs to A4. Existing
step budgets are not reset. Source evidence cannot expand action permissions.

## Delivery storage, issue #8 — draft typed handoff to #5

Stacked on memory PR #7; migration 005 preserves 001–004. Contract definitions:
`contracts/delivery.py`. Store implementation: `shared/delivery_store.py` composed
into existing Store. No network IO, transport, callback parsing or worker assembly
is implemented here. Murtazo must review/agree this typed handoff before wiring it.

- `claim_whatsapp_delivery(worker_id, lease_seconds=60)` returns DeliveryClaim or
  None. Worker ID <=100 chars, lease 5–300 seconds. Claim contains action/agent/task
  IDs, recipient, content, persisted link_generation, worker_id, attempt_token and
  deadline. It atomically changes queued/due deferred to sending. Expired sending
  becomes unknown, including attempts that may not have dispatched: conservative
  recovery avoids blind resend. Unknown/accepted/failed/cancelled are not reclaimed.
- `authorize_whatsapp_send(claim, business_id=..., phone_number_id=...)` returns
  SendAuthorization: permitted with authoritative recipient/text, held with reason
  and retry_at, or cancelled with reason. It locks agent then action, validates
  attempt ownership/expiry, current link generation and phone, pause, completed
  reply task, explicit consent, timezone/quiet-hour preferences, trusted inbound
  event timestamp and text length <=4096. Internal academic/plan results are never
  deliverable through this reply path. Source-dependent artifact delivery must use
  a later verified-artifact contract; it is not implicitly authorized here.
- Permitted authorization atomically stamps dispatch_at and business/number IDs.
  Repeating authorization raises LeaseLost. Worker must send immediately using the
  returned payload ONCE. Do not reuse authorization after restarting. There is a
  residual database-authorization/network-dispatch race: pause/unlink after this
  boundary cannot recall an in-flight request. Never claim stronger cancellation.
- `record_whatsapp_result(claim, DeliveryResult)` requires the live owning attempt,
  prior dispatch authorization and matching internal_id. Only accepted (with
  provider_ref), failed or unknown are valid transport evidence. It reconciles
  stored early callbacks if a reference is known. Late/stale result writes raise
  LeaseLost, storage failures are not success, and no result path schedules resend.
- `record_whatsapp_status(event, business_id=..., phone_number_id=...)` accepts
  WhatsAppStatusEvent ONLY after signature validation by Murtazo's assembly.
  Match configured account/number, provider reference AND recipient; never infer
  account ownership from recipient alone. Record event evidence idempotently.
  delivered/read aggregate to delivered; failed overrides sent/accepted; sent
  cannot override failed; delivered never regresses. Read evidence remains in the
  event record, not a fabricated aggregate read state.
- Callback-before-response is persisted unmatched and reconciled when the exact
  provider reference is saved. Callback and result writes serialize by reference.
  Orphans are retained seven days, capped at 10,000 with an explicit failure when
  full. Expired orphan cleanup occurs on callback ingestion. Without a known
  provider reference (lost send response), an orphan stays unmatched; manual/provider
  reconciliation is required and no automatic resend is permitted.

Trusted assembly calls `record_whatsapp_inbound_time(provider_id, sender, event_at)`
after signature validation AND successful durable inbound ingestion. It requires
a persisted inbound ID matching the current phone/link, timezone-aware provider
event time and at most five minutes future skew; stored time is capped to receipt
and never moves backwards. Old signed events do not reopen an expired 24-hour
window. Receipt-only `last_inbound_at` is not used for send eligibility. Existing
links retain unknown event time. New link generations are random; historical reply
rows without a proven generation are cancelled at authorization, never backfilled
with assumed permission.

`set_communication_preferences(verified_user_id, consent=bool, timezone=IANA,
quiet_start=0..23, quiet_end=0..23)` persists explicit account-scoped preferences.
Equal start/end explicitly disables quiet hours; overnight ranges are supported.
No preference rows are inferred for existing students. Missing preferences,
revoked consent, pause, unknown inbound time, quiet hours and oversized text hold
sending for a five-minute reevaluation; ownership/result mismatch cancels. No
model/source can set preferences by calling an untrusted interface.

IMPORTANT REMAINING GAP: an expired conversation window returns held with
`approved_template_required`. This PR intentionally does not invent an approved
template name, parameters or permission. Approved-template configuration/payload
support needs the next jointly agreed contract before proactive >24-hour sends
can work. Murtazo's transport may prepare templates independently, but must not
bypass this hold. Setup/API preference endpoints, timestamp parser wiring, delivery
worker and signed callback assembly remain Murtazo's tasks. No live send enabled.

## A3 draft artifacts and verification — issue #10 (internal, not wired)

Migration 006 adds private immutable draft payloads and append-only check reports.
Stack dependency: #9 → #7 → integration baseline. No earlier migration modified.

`save_draft(lease, DraftArtifact, request_key)` is fenced to a running academic
responsibility task. It persists title, body, structured claim/quote/source-version
citations and disclosure as `review`, with the responsibility's memory revision.
The same task/key/payload returns the same draft; changed payload conflicts. New
keys create revisions as new artifact IDs. Ordinary conversation tasks cannot
save academic artifacts. Student retrieval through `artifact(verified_user_id,id)`
is private and reports `stale` if source memory changed. No HTTP routes or model
drafting tools are exposed by this increment.

Only `runtime.verification.verify_artifact(store, model, settings, lease, id,
policy=CoursePolicy, rubric=list[RubricItem])` can use the internal readiness commit.
Callers must not expose `_commit_artifact_check` to a model or API. Model responses
alone never change state. Structural checks require current bound source versions,
exact quotes, cited claims present in the draft, a bounded nonempty source-backed
rubric and explicit source-backed course policy. Prohibited, limited or unknown
policy cannot finalize this full-draft path; other permitted assistance belongs
to its own workflow. Required disclosure must appear in the body.

Next, a separate reviewer call through existing ModelClient assesses all citations
against full current sources, all rubric items against the body, uncited claims,
policy classification, disclosure sufficiency and completeness of the supplied
rubric. Structured arrays must match input cardinality; every claim must be
supported and every rubric item covered. Unsupported/uncertain/missing/invalid
assessments cannot pass. Missing/older-than-24-hour evidence blocks before inference;
this is a conservative starting freshness rule, not proof sources are up to date.
The model may still misjudge support or miss requirements: this is fallible semantic
assessment, not a guarantee of correctness or instructor approval.

Each completed check persists policy/rubric evidence, errors, assessment and usage;
pass updates state to ready, failure to needs_revision. Drafts remain readable in
review before checks, preventing a verification deadlock. Provider failure leaves
the draft unready and propagates to the caller for normal bounded retry handling.
Final commit rechecks lease, pause, task ownership and memory revision; a concurrent
source change cannot approve old work. Persisted ready state is historical evidence
of checks at that time; consumers must check stale and revalidate current permissions
before sharing. It is not authorization to send, submit or disclose anything.

This stage supplies an internal boundary only. Draft generation tools, rubric/
policy extraction, end-to-end worker orchestration, student review/download APIs,
sharing and automatic change-driven revision are still pending. The existing
internal academic worker continues producing working notes, not ready artifacts.

## A3 generation helper — issue #12

`runtime.drafting.generate_checked_draft(store, model, settings, lease,
workflow_key=..., policy=CoursePolicy, rubric=list[RubricItem], max_revisions=2)`
connects current bound evidence, source-policy preflight, generation, saved drafts,
mandatory verification and bounded revision. This is an internal helper, not yet
registered in normal worker dispatch or student APIs. It never sends or submits.

A bounded nonempty source-backed rubric is required. Exact policy/rubric quotes
must match current sources retrieved within 24 hours. Unknown/prohibited/limited
policy blocks before generating assignment text. A separate structured model call
must find the source policy permits the requested work; caller classifications
cannot override it. This model judgment is fallible and needs live evaluation.

Default maximum three drafts: initial plus two revisions (configurable 0–2).
Failures feed the previous draft/report into revision. Policy/evidence failures
stop rather than revise around them. Returns ready, needs_revision or blocked;
none authorizes delivery. It does not complete the task or choose its next step.

Persisted workflow keys (1–100 chars) bind policy, rubric and revision budget;
changed payload under the same task/key conflicts. Saved preflight, draft and
checkpoints recover across attempts under task fencing. Source changes/pause
prevent stale writes. Committed drafts resume at review; reports are reused.
Crashes before persisting inference can repeat model usage; no exactly-once billing
claim. Callers must not use new keys to evade task/account execution budgets.
Automatic source-policy extraction and end-to-end worker wiring remain pending.

## A3 worker dispatch — issue #15

Migration 007 stores immutable drafting-request specifications. Existing worker
run_once now dispatches academic tasks with a persisted request through the checked
draft workflow; tasks without a request retain the internal-analysis path.

Trusted assembly calls `configure_drafting_task(verified_user_id, task_id,
policy=CoursePolicy, rubric=list[RubricItem], max_revisions=2)` only after explicit
student delegation. It requires an owned, current, ready, never-attempted academic
step under an active responsibility, source-backed permitted/disclosure-required
policy and 1–30 exact current bound rubric quotes. It must be configured before the
worker claims it; otherwise configuration fails rather than upgrading active work.
Repeated identical configuration is idempotent; changed configuration conflicts.
A model, connector payload or arbitrary caller-supplied identity cannot authorize
this operation. This change adds no HTTP endpoint or automatic delegation classifier.

The worker reloads the persisted policy/rubric under its fence and calls
`generate_checked_draft` using a fixed task-scoped workflow key. Current sources,
freshness, preflight, draft/checkpoint recovery, pause and revision limits remain
mandatory. Passing saves a private ready_for_review result referencing the artifact
and completes the task via the existing fenced transaction, which also creates the
next responsibility planning job. This path does not create WhatsApp delivery or
imply instructor approval. It does not publish the draft body in ordinary chat.

Blocked policy or exhausted revisions record a private drafting_outcome event and
atomically block the task and responsibility, release the lease and preserve saved
artifacts/checks for review. Other work can proceed. Provider/validation exceptions
use existing bounded retries and redacted error codes. Source-change revocation
prevents old drafts/tasks from completing. Trusted API/connector assembly must still
coordinate how delegation, policy evidence and rubric extraction reach this boundary;
Murtazo owns that assembly. Automatic task selection for drafting remains future.

## Private WhatsApp connection read — issue #18, requested by #17

`Store.whatsapp_connection(verified_user_id)` returns None before provisioning;
otherwise `{linked: bool, phone_last4: str|null, preferences: object|null,
latest_delivery: object|null}`. Preferences, when saved, contain consent (bool),
timezone (IANA string), quiet_start and quiet_end (integers). Explicit false/zero
values are preserved. Missing preferences remain null. Latest delivery, when any,
contains state (existing persisted enum), reason (nullable controlled hold reason)
and retry_at (nullable aware datetime, serialized as ISO by API assembly).

State `sending` means a pending attempt, not confirmed delivery. accepted means
provider acceptance; only delivered reflects recipient delivery evidence. unknown
must remain visibly uncertain. This is the latest historical account action, not
necessarily a send for the currently linked generation. On unlink, phone_last4 is
null and linked false; explicit saved preferences and historical delivery remain.
Return no full phone, source/result text, account IDs, challenge/hash, worker IDs,
attempt tokens or secrets. The query uses one statement snapshot. Database errors
propagate; do not replace them with disconnected/default success state. Caller
identity must come from verified auth, never a model or arbitrary request body.

Existing Settings now includes optional whatsapp_business_number (environment:
AGENT_WHATSAPP_BUSINESS_NUMBER), default None, validated 7–15 digits with nonzero
first digit, no plus/spacing. This is a PUBLIC destination number, distinct from
Meta's internal phone_number_id. No guessed/default number is configured. This is
shape validation, not proof the business owns/configured the number.

Murtazo owns authenticated GET /v1/whatsapp assembly, public configuration/readiness
fields, proxy allowlist and student controls under #17. No app/frontend endpoints
are added here. No migration, connection authorization or sending permission is
introduced. Approved-template policy/configuration remains a separate Codex-owned
shared-contract task; expired-window delivery stays held.

## Approved reply templates — issue #21 (review before worker opt-in)

Settings adds whatsapp_approved_templates (max 20 ApprovedTemplate entries, default
empty) and whatsapp_reply_template_key (default None). Environment names use the
existing AGENT_ prefix. Configuration is trusted server/operator input, never a
student API or model/source tool. Operator must verify actual provider approval for
the exact account/name/language/body schema; provider_approved=true is an explicit
configuration assertion, NOT a provider approval lookup performed by Wrytely.
No real template/name/approval is configured by this code change.

ApprovedTemplate fields: key, name (lowercase letters/digits/underscore), language,
business_id, phone_number_id, provider_approved (literal boolean True), body_parameters
(tuple of 1–10 TemplateParameter). Each parameter has source literal/reply_text,
optional literal value, and max_length 1–1024. Literal values must be nonblank and
fit the bound; reply_text cannot set literal. Exactly one reply_text parameter is
required to carry the complete authorized reply. No notification-only substitution
or truncation is allowed in this first contract. Static transport templates may
exist, but this authorization path does not use them to claim answer delivery.

`authorize_whatsapp_send` adds supports_templates=False, approved_templates=(),
reply_template_key=None. Existing workers remain held for expired windows, even if
operator templates exist. Murtazo must review and explicitly opt in a worker that
can branch on SendAuthorization.payload.kind. TextPayload is {kind:text,text};
TemplatePayload is {kind:template,key,name,language,body_parameters}. For permitted
text, legacy authorization.text is preserved. For permitted template, legacy text
is None: worker MUST consume the typed payload, not fall back to claim.content.

For expired conversation windows only: match exactly one selected approved key,
verify configured business/number, populate only allowed parameters, and ensure
the entire reply fits. Missing key/approval/capability remains approved_template_required;
wrong account holds template_account_mismatch; invalid/oversized body holds
template_parameter_invalid. Existing link, consent, pause, quiet hours, known trusted
inbound time and completed reply requirements remain enforced. No body truncation,
model-selected template or new recipient permission. Within-window text is unchanged.

Dispatch authorization atomically records delivery_authorized evidence in the
existing private episode ledger (task ID, action ID, owning attempt, typed payload).
The one-use dispatch fence and accepted/failed/unknown/status correlation remain
unchanged. This is no new migration. Existing send/network cancellation race and
unknown-outcome rules still apply. Murtazo owns passing Settings values/capability,
dispatching payload to the existing adapter once, and adding worker/API tests after
agreement. No transport/worker/app code was changed by Codex in this increment.

## Unsuccessful Meta call evidence — issue #39

MetaModelClient raises ModelCallFailed (a RuntimeError) for received non-completed
responses and HTTP status failures. evidence() returns only controlled status,
HTTP400–599 or null, allowlisted provider code/unknown/null and nonnegative known
input/output token counts or null. No output, provider message/body, response ID,
credentials or source text is included. Null usage is unknown, never zero cost.
Incomplete responses remain unsuccessful and cannot be replayed as final answers.
No transport retry or model/token limit is changed.

The runtime worker saves this metadata as a private fenced model_failure event
before its existing bounded retry/block behavior. These events are excluded from
model-turn replay. If fencing is lost (for example pause), no event is committed;
operator reservations must remain until reconciliation. This is failure evidence,
not a cumulative billing cap, and does not release any reservation automatically.

## Pause recovery and execution-failure allowance — issue #41

Store.set_paused keeps its verified-user/boolean interface and agent-row return.
Pausing atomically revokes each live running task lease, records one trusted private
control_interrupted event per interrupted claim, and returns that task to ready.
The paused agent cannot be claimed. Resuming never restores the old token; a fresh
claim has a new token and monotonically larger attempt number. Existing committed
model/tool/draft checkpoints remain available under the fresh fence.

max_attempts bounds execution/crash attempts separately from recorded control
interruptions. Claim and retry subtract distinct interrupted claim numbers; repeated
Pause while already paused does not grant extra allowance. An already expired
claim remains an ordinary crash, and subsequent real failure still exhausts the
configured allowance. No attempt number is decremented or reused. Source-revision
and responsibility fences remain mandatory. No schema or HTTP payload change.

Pause cannot cancel a provider call already in flight. Its late result cannot
commit through the revoked lease. Unknown/billable interrupted usage must retain
its operator reservation; this recovery mechanism is not a billing cap. Repeated
user controls may cause more claims, so cumulative per-account/global inference
budgets remain a separate M4 gate before public pilot. Nothing starts a worker,
resumes outbound sends or changes consent by itself.
