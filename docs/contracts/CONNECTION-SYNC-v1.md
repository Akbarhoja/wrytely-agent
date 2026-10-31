# C1/C2 v1 — connection and sync proposal

Issue [#47](https://github.com/Akbarhoja/wrytely-agent/issues/47).
**Proposed, not implemented or agreed.** Akbar/Codex owns shared models, persistence,
migrations and authorization. Murtazo owns public HTTP/OAuth assembly, Canvas extension,
Outlook adapter and network IO. Accept this interface in #4/#47 before dependent code.
This first slice of P0-A3 covers C1/C2; C3–C7 still need their own agreement.

## Connection identity and lifecycle

A connection belongs to the verified Clerk user/agent. Store server-generated UUID,
provider (canvas_extension or outlook), provider origin, provider subject, device or
mailbox identity, generation, state, allowed capabilities and lifecycle times.
The student must already be provisioned. Public input never supplies an authoritative
owner. Canvas origin is explicit HTTPS allowlisted configuration, not an arbitrary
URL an untrusted page can ask the extension/server to fetch.

States: pending_identity, connected, reconnect_required, disconnected. Connection
history remains private; retention/deletion policy is separately decided before pilot.
Every reconnect, account switch, revoke or credential replacement advances generation.
Late writes, jobs and sync claims from the old generation are rejected. Disconnect
revokes future reads/commits/actions but does not pretend to erase prior evidence.

Canvas subject is read through the student's current session, checked at the start
and end of each batch. A subject change aborts the batch and requires relinking; do
not relabel an old course cache as belonging to the new login. Client reports remain
untrusted evidence: extension authentication proves who uploaded, not provider truth.

Outlook mailbox identity is obtained by verified OAuth/token/provider flow in M's
assembly, never an email string typed into a body. Use one-use expiring state bound
to Clerk session, exact redirect and PKCE where supported. Reject account mismatch,
state replay and unapproved scopes; redirect/notification validation belongs to M.

## Pairing credential

Proposed shared operations (internal methods, not names of public routes):

- create_pairing(verified_user, allowed_origin): returns private device challenge,
  human code, expires_at. Random challenge is one-use, ten-minute lifetime. Store
  only hashes; rate-limit create/redeem and bind origin/account before issuing access.
- redeem_pairing(code, device_public_id): atomically consumes the valid challenge
  and returns connection ID, generation and one-time displayed ingestion bearer.
  No race can issue two active credentials from one challenge. Invalid/expired/replayed
  codes have one public error class; bounded attempts prevent code enumeration.
- bind_canvas_identity(credential, origin, provider_subject): connects the pending
  paired device only to its configured origin. An already bound subject cannot change
  silently. This scoped method is allowed only for an authenticated paired extension.
- rotate_or_revoke(verified_user, connection_id): scopes ownership, advances generation,
  revokes credential and fences open syncs. Never accepts model authorization.

Default: pairing creates a pending-identity credential that can bind subject but cannot
upload course data yet. After binding it gains canvas:sync only for that connection.
Credential: at least256 bits random; digest only on server; 30-day default expiry;
renew through authenticated student pairing, not perpetual silent access. Client stores
it in extension-private storage, never content scripts/page DOM. Configure exact
credential lifetime before pilot. No Canvas cookie/password leaves the browser.

Outlook refresh credentials differ: encrypted secret storage with operator-managed
key/handle, scoped access and no value in safe projections/model prompts/logs. An
outlook connector worker receives a secret handle under its service role, not the
extension ingestion credential. The exact existing secret service is chosen at setup.

## Sync envelope and limits

Illustrative JSON values below are synthetic. UUIDs represent server-issued identifiers.

```json
{
  "schema_version": 1,
  "connection_id": "00000000-0000-4000-8000-000000000001",
  "generation": 1,
  "scan_id": "00000000-0000-4000-8000-000000000002",
  "batch_key": "scan-1-assignments-page-1",
  "subject": "canvas-user-fixture",
  "resource": { "course_id": "course-101", "kind": "assignments" },
  "observed_at": "2026-10-30T16:00:00Z",
  "items": [
    {
      "provider_id": "assignment-17",
      "provider_updated_at": null,
      "title": "Essay",
      "reference": "https://canvas.example.edu/courses/101/assignments/17",
      "fields": { "due_at": "2026-11-02T05:59:00Z", "points_possible": "20" },
      "content": "Write an essay using the attached rubric.",
      "coverage": "partial",
      "missing": ["rubric_attachment"]
    }
  ],
  "coverage": { "state": "partial", "reason": "more_pages", "seen_count": 1 },
  "next_cursor": "opaque-provider-cursor-or-null"
}
```

### Canonical content digest — executable reference candidate

[contracts/source_digest.py](../../contracts/source_digest.py) is the proposed v1
reference; [fixed vectors](../../tests/fixtures/source_digest_v1.json) include exact
canonical UTF-8 and SHA256. It is not consumed by ingestion/runtime yet. M can port
and run the same vectors in JavaScript before agreeing the wire version. Clients omit
content_digest in uploads; server computes it and returns it in the commit receipt.

Digest envelope has exactly digest_version=1, kind, title, content, fields, coverage
and missing. No collection timestamps, provider updated_at, source identity, cursors,
URLs or credentials enter the content digest. Identity is a separate key including
connection namespace, origin/mailbox, course, resource kind and provider object.
Reference links remain provenance; a rotating signed download URL does not create a
new document revision. Both provider updated_at and content digest are retained.

Normalize strings to Unicode NFC and LF line endings. Preserve spaces, trailing
newlines, casing and ordinary array order. Normalize object keys the same way and
reject collisions. Sort keys by Unicode scalar value (JavaScript's default UTF-16
sort is insufficient for some astral keys); UTF-8 encode compact JSON with no ASCII
escaping or incidental spaces. missing is a sorted unique normalized string set.
Only null, booleans, safe JSON integers (absolute value <=2^53-1), strings, lists and
objects are allowed; reject floats/NaN/infinity, invalid Unicode and depth>16.
Decimal quantities use adapter-normalized base10 strings, not binary floats.

Recognized date field names due_at/unlock_at/lock_at/submitted_at/sent_at require
RFC3339 with an explicit offset and seconds, maximum6 fractional digits; normalize
to UTC with exactly6 fractional digits and Z. Null remains null; naive dates and
natural-language dates are not guessed. Calendar-only dates need a separate date
field plus source timezone and cannot silently become midnight due_at.

Provider mapping field sets (include null for unknown values; v1 mapper rejects
undeclared fields before canonicalization, rather than passing entire raw objects):

| Kind             | fields content affecting meaning                                                                              |
| ---------------- | ------------------------------------------------------------------------------------------------------------- |
| course           | course_code, timezone, enrollment_state                                                                       |
| assignment       | due_at, unlock_at, lock_at, points_possible, submission_types, rubric (ordered source-backed rows), published |
| submission       | assignment_id, submitted_at, workflow_state, attempt, late, missing                                           |
| grade            | assignment_id, score, points_possible, grading_type, grade, grade_basis                                       |
| syllabus/page    | page_id, module_ids (sorted stable IDs), source_format                                                        |
| discussion/entry | topic_id, parent_entry_id, author_role, required_initial_post, due_at                                         |
| announcement     | author_role, posted_at, announcement_id; posted_at is adapter-normalized RFC3339                              |
| email            | immutable_message_id, sent_at, sender, subject, attachment_manifest                                           |
| file_segment     | parent_object_id, extraction_version, slot, total_slots, source_format                                        |

Lists whose order is irrelevant (module_ids/submission_types) are sorted by the mapper;
rubric/thread/content order remains significant. Source wrappers validate required
field sets; the reference canonicalizer only defines portable bytes, not provider
schema validation. Additional resource fields require mapper/contract revision.

Large documents: one stable parent object, deterministic extraction_version and slots
such as page:1:chunk:0. Stable section key = parent object + extraction_version + slot;
slot content hash is revision data, not identity. Manifest contains ordered slots,
content digests, expected count, source-file digest and completeness. Changed extraction
can resegment the object and invalidate bindings; do not silently reuse offset citations.
Stage segments during a scan. Promote a complete parent manifest only after all expected
slots are committed and verified. Partial new extraction records failed coverage without
replacing the previously complete parent/source payload. Discovery may report the new
partial evidence, but draft retrieval keeps the prior version labeled historical until
an adequate current version is available. This does not bypass freshness checks.

[Vector1](../../tests/fixtures/source_digest_v1.json) supplies an assignment input, exact
canonical bytes and hash. Read it directly rather than copying an explanatory placeholder.
The reference tests show unchanged content across repeated successful checks can share
one digest; collection check records update separately under the receipt rules below.

Proposed initial hard bounds:50 items/batch,1MiB JSON body,128-character batch key,
4,000-character cursor,24,000 text characters/segment. Larger documents use stable
object + segment identity, segment count/digest and full extraction manifest. An
incomplete segment set cannot be labeled complete or replace a previously complete
object with an empty value. Do not split an assignment into unrelated commitments.
Actual file download/extraction limits and supported types need M's confirmation.

Coverage: complete, partial, restricted or unsupported. Controlled reasons include
more_pages, login_required, permission_denied, initial_post_required, rate_limited,
provider_unavailable, extraction_failed, size_limit, cursor_invalid and unsupported_format. Resource coverage is separate
from item coverage and accessible-course enumeration coverage. No raw provider error
body is returned to a student. Unknown course/file contents remain unknown.

## Begin, resume, commit and finish — exact proposed shared signatures

Python names below are proposed internal Store methods. M maps them to HTTP, with
verified identity/credential context; no route is implemented by this document.

- begin_sync(actor, connection_id, generation, subject, scope_revision, begin_key)
  returns {scan_id, scan_sequence, lease_token, lease_expires_at, checkpoint}.
  begin_key is a client-generated128-character replay key. Same key/body returns the
  existing scan; same key/different body conflicts. Only one live scan per connection.
- resume_sync(actor, scan_id, generation, resume_key) returns the same shape with a
  fresh lease_token and last durable checkpoint. Lease duration300 seconds. Repeated
  identical resume_key returns its prior response; if expired again, use a fresh key.
  A scan lasts at most24 hours from start; after that use a new scan and do not promote
  incomplete resource enumeration to complete. Resume never advances generation.
- commit_sync_batch(actor, scan_id, generation, lease_token, batch_key, expected_checkpoint, envelope)
  returns {receipt_id, scan_id, batch_key, batch_digest, source_versions, checkpoint,
  coverage, replayed}. Source versions list stable provider_id, version_id and server
  content_digest. Checkpoint includes resource key, next_cursor, committed batch sequence
  and scope_revision. Batches serialize on scan; no parallel cursor advances.
- finish_resource(actor, scan_id, generation, lease_token, resource_key, finish_key,
  expected_checkpoint, *, outcome, reason) returns a durable resource receipt with
  coverage=outcome, reason, seen_count, finished_at, checkpoint and
  source_manifest_digest (null unless a complete manifest is verified). outcome is
  complete, partial, restricted or unsupported. Complete requires reason=null, no
  remaining page and every expected segment; empty complete enumeration is valid.
  Other outcomes require a controlled reason and explicitly terminalize incomplete
  collection without promoting a manifest. Matching key/body replays its receipt.
- finish_sync(actor, scan_id, generation, lease_token, finish_key) returns scan summary,
  discovery coverage and separate per-course/resource coverage. All selected resources
  must have terminal receipts, including controlled partial/restricted/unsupported
  receipts; aggregate state is partial if any required resource is not complete.

### Terminal resource receipts and abandoned scans

A resource is open until finish_resource commits its terminal receipt. A collector
that cannot finish a page or segment calls it with outcome=partial and a reason such
as cursor_invalid, extraction_failed, size_limit, rate_limited or provider_unavailable.
For permission_denied/initial_post_required use restricted; for an unsupported content
format use unsupported/unsupported_format. login_required requires relinking when the
connection no longer authenticates; it cannot override generation or credential fences.
These are enumerated codes, never raw provider messages. A retryable failure may instead
leave the resource open and resume within the scan lifetime; retry is not required to
record an honest terminal partial outcome.

All finish calls authenticate the current actor/generation/scope before receipt lookup.
An exact committed finish_key/body replays the original receipt after lease expiry or
renewal, with no timestamp changes. Body includes resource, expected checkpoint, outcome
and reason but excludes lease_token. Changed body with that key conflicts. An unseen
finish requires the current live lease and exact durable checkpoint, even for partial
outcomes. Incomplete complete requests return incomplete_segments or remaining_pages;
they cannot silently downgrade to partial. Termination and receipt persist atomically.
A terminal resource rejects further batches or a different terminal outcome in that
scan (resource_terminal); collect again in a new scan rather than reopen/promote it.

Example: after committing page1 of a document with three expected segments, segment2
extraction fails. finish_resource(..., outcome=partial, reason=extraction_failed)
retains page1 as staged historical evidence, records its checkpoint/count and null
source_manifest_digest, and leaves the previous complete parent unchanged. No pending
cursor is fetched or counted as completed. This receipt allows finish_sync to close
once every other selected resource has a terminal receipt; its aggregate remains
partial. Successfully committed independent complete items keep their own check records;
the failed resource/parent does not advance last_successful_check or last_complete_scan.
Termination finished_at records the attempt, not freshness. Partial enumeration never
supplies deletion evidence. Normal draft freshness/coverage gates still apply to all
retained evidence, including the earlier complete version.

If the client disappears entirely, the server does not invent a client finish receipt.
Instead a trusted expiry operation marks the scan expired at its24-hour deadline,
fences new commits and records each still-open resource as aborted/scan_expired in
internal scan history (student coverage=partial). No manifest promotion, new successful
check, deletion or model authority follows. aborted is an internal scan termination
state, not a fifth collector outcome; finish_sync cannot turn an expired scan into a
success. A disconnected/replaced generation is similarly aborted by lifecycle handling
with reason=connection_changed. Completed receipts remain historical and private.

### Selected-course consent

Initial authenticated consent grants course discovery plus a user-selected set of
courses (or explicit all accessible active courses). Store scope_revision, selected
course IDs/mode and resource types. IDs come from same-session discovery, not arbitrary
input. Discovery lists course identity/metadata only; it does not grant course-content
collection automatically. Selection can be completed through the paired extension/UI.
A later newly found course is not selected under explicit-set consent; all-active mode
includes it only within its recorded scope. Change of course/resource selection advances
scope_revision and connection generation, fencing scans and preventing late old uploads.
No fetch outside scope and no source ingestion outside scope. M's counts-only feasibility
probe has separate live authorization and does not imply product-wide collection consent.

### Replays and browser termination

1. Authenticate current credential, owner, connection generation, subject and scope
   before any receipt lookup. Disconnected or replaced credentials cannot read receipts.
2. For an already committed batch, compare canonical envelope digest (includes observed_at,
   item payload, resource, cursor and coverage and expected_checkpoint; excludes lease_token and transport auth).
   Same scan/key/body returns the original receipt even after the lease expires or is
   renewed. No freshness timestamp or cursor changes on this replay. Changed body409.
3. For an unseen batch, a current matching live lease is mandatory. Old lease409
   lease_expired/lease_replaced; resume then retry the SAME captured envelope/batch key
   using the new token. Do not change observed_at merely to retry an old fetch.
4. If browser terminates after commit but before acknowledgment, resume scan, resend
   the exact captured envelope, obtain the previous receipt, then fetch from the saved
   next_cursor. If no commit occurred, new lease allows that exact batch to commit once.
5. If the client lost its envelope, inspect the resume checkpoint and refetch the current
   resource page using a new batch key. Source digest prevents duplicate content events;
   resource/sequence constraints reject rewinding the checkpoint as a new earlier page.
   A prior manifest is never declared complete from a missing client checkpoint.
6. Lost or invalid provider cursor becomes partial/cursor_invalid. Finish partial scan
   or start a new scan for bounded rescan; no arbitrary cursor URL fetch. Link/delta values
   stay private opaque values and M validates exact provider origin/endpoint before IO.
7. Transaction persists versions, check records, events, receipt and checkpoint atomically.
   Failure rolls back all of them;503 response never advances a cursor. Checkpoint/scan
   generation rejects older writes. Lease heartbeats cannot revive expired/replaced claims.

Receipt example: {receipt_id: receipt-1, scan_id: scan-1, batch_key: page-1,
replayed: true, checkpoint: {resource: course-101/assignments, next_cursor: opaque-2,
sequence: 1, scope_revision: 1}, coverage: partial}. IDs are illustrative. Replay has
identical receipt/time/version fields; only the replayed response flag differs.
Error example:409 {code: lease_expired, action: resume_scan};409 {code: replay_conflict,
action: inspect_checkpoint};403 {code: course_not_selected, action: update_consent};
422 {code: incomplete_segments, action: resume_resource};503 {code: storage_unavailable,
action: retry_same_batch}. These controlled errors contain no raw content/cursor/token.

A complete course-discovery receipt proves only enumeration. Assignments, discussions,
files, grades and every selected course have independent receipts. A403 on discussions
cannot overwrite the earlier complete syllabus or mark the whole course empty. Known
objects missing from a full authoritative scan become missing_pending_confirmation;
explicit deletion/reconciled authoritative evidence is required for deleted state.

Outlook ingestion uses the same observations/receipts under trusted worker identity;
webhooks merely queue a read. Subscription renewal, delta token invalidation, per-folder
catch-up and opaque cursor validation live in M's adapter. Cursors/secret handles are
private, never exposed in normal student status. Provider acknowledgments follow durable
receipt; queue notifications are hints and can be replayed from committed events.

## Freshness and source changes

Keep source_versions.retrieved_at immutable as original observation evidence. A separate
check record binds exact content version, connection generation, server received_at,
client/provider observed_at, resource coverage and outcome. last_successful_check is
updated only after a valid successful check. Failed reads update last_attempt only.
Reject future client observations >5 minutes and expired/inconsistent scan generations;
old offline uploads can be preserved as historical evidence but cannot refresh current
coverage. Replays return original receipt without moving freshness time forward.

One policy consumes these check records for summary, requirements, drafting, semantic
review and final readiness. Fresh data can still have partial coverage. Unchanged source
can be recently checked. Changed source invalidates affected work as today; P4 adds
replanning rather than removing the fence. No timestamp-only source versions.

## Safe projection and errors

Student connection status: provider, origin alias, connection state/generation,
credential expiry/reconnect-needed, last attempt/success/complete scan, per-course
coverage and count or unknown. No bearer/hash, OAuth code/token, cursor, cookie,
provider payload or full mailbox identity in ordinary readiness output.

Public assembly maps controlled errors: authentication_required(401), not_found(404,
including non-owned), conflict(409), expired_pairing(400 generic pairing failure),
invalid_batch(422), payload_too_large(413), rate_limited(429), temporarily_unavailable(503).
Stale generation/lease maps to409 with reconnect/resume action as appropriate. Storage
failure is503, never successful empty data. Keep correlation IDs private/redacted.

## Required contract tests and open agreements

- Two users cannot read/commit/revoke each other's connection, receipt or source.
- Pairing replay/race/expiry, credential expiry and wrong origin are rejected.
- Login account switch aborts; disconnect while a batch is processing prevents commit.
- Same batch replay is idempotent; changed replay conflicts; rollback leaves no event.
- Pagination interruption and incomplete document segments preserve partial status.
- Unchanged successful check refreshes status; replay/failed read cannot fake freshness.
- Source change emits one event; timestamp-only differences do not duplicate assignments.
- Old scan and missing-page/access-denial cases cannot overwrite/delete newer evidence.
- Notification loss/replay plus restart catch-up yields the same private Outlook state.

M must confirm: workable Canvas session/identity validation, download/file extraction
bounds, cursor/checkpoint shape and Outlook provider identity/delta behavior. A must
confirm: additive schema, transaction/fence behavior, credential storage selection and
freshness policy consumer migration. Both approve exact v1 examples before executable
models/store/API work. Consent, provider access and deployment remain separate gates.
