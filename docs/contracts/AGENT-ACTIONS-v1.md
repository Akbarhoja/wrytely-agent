# C3–C7 v1 — agent retrieval, decisions, delivery and operation

Issue [#47](https://github.com/Akbarhoja/wrytely-agent/issues/47), stacked proposal #48.
**Proposed, not executable or agreed.** Complements [C1/C2](CONNECTION-SYNC-v1.md).
Owner A = Akbar/Codex (shared/runtime/contracts); owner M = Murtazo (network/app/web/
extension/deploy). The existing private draft/reply contracts remain effective until
reviewed replacements are implemented. This document does not activate any capability.

## C3 — Private retrieval and semester context

A provides verified-user reads for app consumers and lease-scoped reads for model tools.
M exposes authenticated routes/projections; model tools never take a user_id argument.
Both reads enforce the same student/source connection scope and current generation.

Proposed internal operations:

- list_courses(scope, cursor, page_size): return discovered course IDs/names/zones,
  discovery completeness and per-resource coverage/check times. Default20, maximum50.
- list_commitments(scope, filters, cursor): return obligation type, course, known due
  date/weight, provenance, tracking/work/delegation/submission states and revision.
- find_sources(scope, query, course_ids, cursor): bounded keyword/metadata retrieval
  initially; no new vector service required. Return source/section IDs, cited version,
  coverage/freshness and safe excerpts. Default10, maximum20 results.
- read_source_sections(scope, version_id, section_ids, cursor): return original normalized
  evidence text, stable section IDs and offsets, provenance, content hash and completeness.
  Hard total40,000 characters/tool result, at most20 sections; explicit next cursor.
  Truncation must be labeled with retrievable continuation, never treated as full content.
- read_goal_context(lease): current goal, semester summary, recent committed results,
  outstanding dependencies and pending decisions. Summary includes source references
  and age; it is an index for investigation, not an authoritative substitute for sources.

A scope is derived from the verified session or active task lease, never a source payload.
Disconnect fences new retrieval/model work that requires that connection; historical
private reads follow the agreed retention policy and remain clearly historical. Source
version references are immutable. Current-version validation and freshness/coverage
policy are rechecked at final draft/offer authorization, not just before the first call.

Commitments have independent dimensions: tracking(active/closed/uncertain),
work(not_started/working/waiting/blocked/ready), delegation(unassigned/student/agent/
declined), submission(unknown/student_reported/provider_observed/reopened). An optional
post is not an obligation. Store due-date overrides, course-specific grade basis and
unknown values; raw points_possible does not establish final grade weight.

Extracted obligations and email matches are model candidates. Require source versions
and quoted evidence before promoting them; uncertain matches become a clarification
rather than merging similarly titled assignments from different courses. Stable identity
is connection/course/provider object; cross-source aliases retain both evidence chains.

## C4 — Proposed action intents and WhatsApp dispatch

Meta proposes an action, never permissions or a phone number. A validates/persists an
intent; M consumes an authorized typed dispatch and records actual provider evidence.
Reuse existing delivery store/lease/status handling, extending it rather than adding
another queue or notification implementation.

Illustrative supervisor output (server resolves identities and validates evidence):

```json
{
  "kind": "offer_help",
  "commitment_id": "00000000-0000-4000-8000-000000000010",
  "expected_revision": 3,
  "reason": "The essay requires preparation before Friday.",
  "source_version_ids": ["00000000-0000-4000-8000-000000000011"],
  "requested_work": "private_draft",
  "next_check_at": "2026-11-01T16:00:00Z"
}
```

Allowed first-version actions: investigate (scoped read), offer_help, notify_change,
request_refresh, schedule_check, begin_delegated_step, revise_delegated_work, wait/idle.
The action-kind enumeration does not predetermine the useful task; the model chooses
its specific objective, tool sequence and follow-up based on evidence. No send_email,
post_discussion, submit_assignment, run_shell or arbitrary URL-fetch action exists.

Persist action_id, agent/goal/commitment, expected memory and commitment revisions,
link/connection generations, purpose, evidence, consent reference, payload digest,
server idempotency key, expiration, state and attempt fence. Reject invalid source
references and cross-course/account mixing. Model keys cannot bypass deduplication.
Dedup key derives from commitment + purpose + relevant revision + reminder occurrence.
Re-reading unchanged information never creates another offer. Material changes may
supersede an old offer; decline remains effective unless reconsideration is justified.

M's proposed typed payloads: text, offer_buttons, document, approved_template.
Text/offer/document are eligible only in an open trusted reply window. After24 hours,
a configured provider-approved template may notify the student; after their reply,
continue with the relevant offer. No placeholder approval or arbitrary text inserted
into a template just to bypass restrictions. Template categories/variables/buttons
must match actual account approval. Source data cannot select a recipient/template.

Authorization rechecks verified link generation, consent, pause, source freshness,
current permission, message cap, quiet hours, expiration and payload size, then issues
one-use dispatch authorization. M sends that payload once; no fallback to old claim text.
Three/day default cap applies to unsolicited notifications/offers; replies and requested
results use separate bounded queues. Respect stop/cancel regardless of cap. Unknown
or conflicting preferences ask the student before broadening communication.

Status: queued/held/dispatching/accepted/delivered/unknown/failed/cancelled. Keep attempt
and evidence history. A crash after dispatch but before receipt is unknown; no automatic
resend. Reconcile signed callbacks/provider references where possible. Never call an
accepted request delivered. Cancellation cannot undo a send already in flight; record
late delivery honestly and prevent further actions.

## C5 — Student decisions and controls

M verifies webhook signature and provider account/phone/link, durably ingests provider
message ID, then passes the normalized event to A. Free text remains untrusted content;
student identity comes from the verified link. Duplicate webhook IDs are idempotent.
Button IDs are opaque server-generated tokens bound to offer, link generation,
commitment revision, allowed decision and expiry; no arbitrary task_id from a button.

A exposes apply_student_decision(verified_actor, decision, replay_key) to trusted assembly.
Input kinds: accept_private_work, student_will_do, decline, snooze, request_revision,
pause/resume, cancel_goal, communication_preference. Supplied intent is a candidate;
verify current scope/revision and require explicit clarity for work authorization.
Ambiguous "yes" across several offers causes clarification, not arbitrary acceptance.

Atomic acceptance verifies owner/link, pending offer, expiry/current evidence,
permitted work mode, queue/budget and chosen delivery scope. It creates exactly one
responsibility through existing bound/private draft setup, persists consent and marks
offer consumed. Same key/body returns prior outcome; changed body conflicts. Failed
validation creates no half-configured workflow. Student-do and decline cancel the
agent's pending work/offers for that obligation without deleting useful private results.
Snooze schedules one bounded check; a past or contradictory time needs clarification.

Reading consent, private drafting consent and delivery-to-student consent are recorded
separately. An offer's acceptance can explicitly include sending the result to the
same linked student; it cannot authorize a classmate, new recipient or submission.
Requirement changes do not upgrade scope; material expansion requires another decision.
Silence can preserve a prior formatting choice, never create new delegation or consent.

Free-text interpretation uses Meta with bounded evidence and produces the same typed
decisions as buttons. Only validated decisions change state. Preference requests such
as "during class" need known class intervals or a clarification; do not invent a schedule.
Pause/cancel/unlink follow their current fences and also cancel future applicable checks.

## C6 — Checked files and private delivery

A owns artifact content/checks, rendering and immutable version identity. M owns
concrete storage/network upload, private download routes and WhatsApp media transport.
The model can request rendering a current checked artifact; it cannot supply a file
path, storage bucket, public URL or final readiness assertion.

Proposed sequence:

1. A validates artifact/student/current memory and reserves a rendering job keyed by
   artifact revision + renderer version + format. Permitted formats: docx/pdf initially.
2. A renders bounded content with sources/disclosure preserved, computes checksum,
   validates output and supplies a file descriptor: opaque file_id, artifact/version,
   MIME, sanitized display filename, byte length, SHA256 and check-report reference.
3. M stores the bytes under private agent-scoped storage through the agreed interface;
   storage key is server-generated, never model-controlled. Idempotent same descriptor
   is accepted; changed bytes under one file identity conflict. No finalized descriptor
   until durable upload acknowledgment. Failed/partial uploads are not deliverable.
4. A authorizes document delivery under C4/C5, rechecking current artifact/source state.
   M uploads/fetches the authorized bytes and dispatches to the verified linked number.
   Receipt references exact file checksum/version; provider failure is explicit.
5. Website downloads authenticate the student on every request, use no-store semantics
   and scoped authorization. Prefer authenticated streaming. If a provider needs a
   temporary signed URL, bound lifetime/scope and disclose bearer-link behavior; do not
   claim a URL alone authenticates its reader. No stable public artifact URL.

### Exact proposed byte-stream boundary

M implements put_rendered_file(scope, render_id, descriptor, chunks) -> UploadAck,
where chunks is an iterator of bytes from A's renderer, never a caller-provided path
or arbitrary URL. descriptor has artifact_id, artifact_revision, renderer_version,
format, MIME, sanitized filename, expected_byte_length and expected_sha256. render_id
is a server UUID/idempotency key, not the final downloadable file_id. Initial bound:
10MiB rendered output, chunks at most64KiB, allowed MIME application/pdf or the DOCX
MIME. Stream stops on length overflow, invalid MIME/signature, cancellation or checksum
mismatch. The provider uploader consumes and independently hashes/counts the actual
bytes; an object-store ETag alone is not a verified SHA256.

UploadAck is {render_id, storage_handle, byte_length, sha256, durable: true}; return
only after object storage acknowledges a completed upload and recorded checksum/length
match the consumed bytes. Failed/interrupted upload stays provisional and privately
cleanable, not downloadable. Same render_id and exact bytes/descriptor return its
existing acknowledgment; changed descriptor/body409. Lost acknowledgment reconciles
that exact render_id/checksum, not another student object's filename. Provider IO
never trusts a model-created storage_handle.

A's finalize_render(lease, render_id, UploadAck) rechecks lease, source/artifact revision,
expected checksum/length and approved renderer metadata before creating final file_id.
Only this stored final identity can enter a C4 document intent. A stale upload may be
retained as private historical bytes but cannot be finalized for current delivery.
M supplies open_owned_file(verified_actor, file_id) -> bounded byte stream + stored
metadata for authenticated download; cross-account requests return the same404.

For WhatsApp media, M uploads these exact authorized bytes to the configured account
and records provider_media_id, own file checksum, creation time and actual provider
expiry/revalidation policy. Do not invent a media lifetime if the provider does not
supply one. Expired/unavailable media before dispatch may be re-uploaded idempotently
for the same current file, followed by a fresh dispatch authorization. After unknown
message dispatch, a media refresh is not permission to send again. Signed result/
delivery receipts continue to identify the original action and attempt. Remote media
URLs are not student download permissions and never become stable public file URLs.

Render limits are configured and visible. Draft text, citations and math/tables that
cannot render must return a controlled error. A stale draft remains privately readable
but cannot be silently sent as current. Revocation prevents new dispatch; it cannot
recall a document already delivered to a phone. Keep prior versions on revision and
render/review the new version independently.

## C7 — Durable operation, budgets and recovery

A provides task/supervisor claims, source/goal fences, schedules, accounting and health
projections. M deploys API, runtime, connector and delivery processes, supplies readiness
checks and alerting, and documents shutdown/rollback. One codebase/Store, no second agent
runtime. A readiness flag is not evidence that the provider accepted a live call.

Atomic scheduling stores due_at, agent/goal/commitment revision, reason, coalescing key,
lease/fence and cancellation generation. Only one supervisor episode per student is
active at once; other students remain schedulable. Batch related events and apply a
bounded number of model/tool steps. Earlier urgent evidence can advance a planned check;
unchanged replays do not generate a new model call. Idle records why and when to review.

Budget policy is trusted operator configuration, in integer micro-USD/Decimal, not float
or model input. Before every model call, atomically reserve a conservative maximum for
bounded input and output at a recorded rate version, against workflow/account/global
limits and a request-count ceiling. Reservation + dispatch intent commits before the
network request. Reject calls if pricing or upper bound is unknown. Cover all supervisor,
extraction, drafting, review, free-text interpretation and retry calls; do not meter only
the final reply. Configuration changes cannot erase outstanding reservations.

Known response usage replaces its reservation with actual cost only after validation.
Unknown/incomplete/timeout outcomes keep the unreconciled reservation unless known usage
fully accounts for the request. A pause or expired lease must not erase accounting:
provider settlement uses a separate immutable call/reservation identity, without letting
that late result commit task progress. Only trusted provider usage/operator reconciliation
can settle ambiguous cost; record evidence and history. This extends existing fenced
failure logs, which alone are not enough for cross-lease accounting.

A service crash before dispatch can leave a conservative reservation; after dispatch
unknown remains reserved. Never blindly issue the same request again as free work.
Controlled retries need fresh reservations and task-attempt limits. Spending caps stop
new paid calls; already reserved calls can complete and settle. Credits/email alerts
are not hard caps. No new allowance is implied by this proposal.

Health projects last worker heartbeat, oldest due task, pending/blocked/unknown counts,
last successful provider sync/delivery and budget remaining/reserved. Expose no private
text or credentials. M sets operational alerts for stalled queues/outages. A durable
operator stop prevents new claims/dispatch; existing in-flight activity has honest
limits. Restart reclaims expired leases, resumes committed checkpoints and reconciles
outbound/call uncertainty without inventing completion. Model reasoning/checkpoint
payloads remain private; no raw provider message in shared logs.

## Interface acceptance and implementation order

1. M confirms retrieval projections, normalized inbound/button constraints, actual
   template/media limitations, upload/download interface and process-health needs.
2. A confirms atomic persistence/consent, source retrieval bounds, independent accounting
   settlement and additive schema/migration order. Recheck the deployed migration ledger.
3. Record agreement with version/commit in #47 and CONTRACTS.md. C1/C2 storage is first;
   C3 memory next; C5 intent and C4 outbox follow the supervisor; C6 files and C7 runtime
   limits are implemented in their work orders. Hard budgets precede any live always-on run.
4. Keep old consumers working until their owner migrates. No model/client call can access
   proposed operations just because documentation exists. Contract changes get separate
   PR review before dependent implementation.

Required cases: cross-account retrieval/file/button denial; lost/stale/paginated source;
unchanged polls; conflicting email dates; duplicate acceptance; changed rubric after
acceptance; stale/expired offer; pause/unlink during model/render/send; revision mismatch;
unknown provider send; file mismatch; expired media URL; out-of-order callbacks; simultaneous
students; budget racing/reservations; interrupted model call settlement; worker restart;
quiet hours and capped unsolicited messages; idle episodes without unnecessary inference.
Cite real delivery/checked artifact only after live evidence exists. Scripted cases alone
do not close those gates.
