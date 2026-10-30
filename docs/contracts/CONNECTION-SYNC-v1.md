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
      "content_digest": "SERVER_RECOMPUTES_CANONICAL_DIGEST",
      "coverage": "partial",
      "missing": ["rubric_attachment"]
    }
  ],
  "coverage": { "state": "partial", "reason": "more_pages", "seen_count": 1 },
  "next_cursor": "opaque-provider-cursor-or-null"
}
```

The digest value above is explanatory, not a valid hash. Shared code defines canonical
normalization and recomputes a SHA256 digest from relevant fields/content/coverage.
Stable identity includes connection namespace, origin/mailbox, course, resource kind
and provider object ID. Email IDs use provider-supported immutable identity where
available; message movement is not automatically new academic work. Provider timestamp
alone cannot replace digest comparison. Time fields are UTC-aware; preserve course zone.

Proposed initial hard bounds:50 items/batch,1MiB JSON body,128-character batch key,
4,000-character cursor,24,000 text characters/segment. Larger documents use stable
object + segment identity, segment count/digest and full extraction manifest. An
incomplete segment set cannot be labeled complete or replace a previously complete
object with an empty value. Do not split an assignment into unrelated commitments.
Actual file download/extraction limits and supported types need M's confirmation.

Coverage: complete, partial, restricted or unsupported. Controlled reasons include
more_pages, login_required, permission_denied, initial_post_required, rate_limited,
provider_unavailable, extraction_failed and size_limit. Resource coverage is separate
from item coverage and accessible-course enumeration coverage. No raw provider error
body is returned to a student. Unknown course/file contents remain unknown.

## Begin, commit and finish

1. begin_sync authenticates connection/generation/subject and issues server scan ID,
   lease and bounded resource checkpoint. Only one active writer per connection.
   Batches are sequential per scan; store a monotonic scan sequence on the server.
2. commit_sync_batch checks lease/generation, size, item identity, time and cursor.
   Ownership is derived from the credential/service role. Persist source versions,
   coverage, checks, deduplicated change events and checkpoint in one transaction.
3. Same scan/batch_key plus same canonical body returns its previous receipt. Same
   key/different body conflicts; failed transaction advances nothing. Response contains
   receipt_id, accepted counts and controlled coverage, never a guessed agent decision.
4. Distinct batches can legitimately observe the same object; identical content adds
   last_checked evidence but no version/event. Older scans cannot replace newer facts.
5. finish_resource marks complete only after all pages/segments were received, validated
   and committed. Explicit empty complete scans differ from failures/partial scans.
   Lease expiry resumes a checkpoint under a new claim; stale old batches are rejected.
6. A full authoritative scan may mark previously seen objects missing; retain history
   and label missing separately. Require explicit provider deletion/authoritative
   reconciliation before confirmed deleted state. Never infer deletion from403/429,
   unavailable tab, unread page or interrupted scan.

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
