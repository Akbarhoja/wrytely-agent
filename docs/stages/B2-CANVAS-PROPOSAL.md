# B2 Canvas discovery and monitoring proposal

Status: **Proposal for owner/interface agreement, not implemented or authorized.**
Requested by founder correction [#43](https://github.com/Akbarhoja/wrytely-agent/issues/43)
and coordination6515094526. Canvas discovery, ongoing reads and proactive work
offers are required acceptance. Existing manual snapshots remain useful evidence
infrastructure; they do not satisfy this requirement. No institution was contacted,
credential obtained, OAuth grant accepted or student course read in preparing this.

## Product path and ownership

Student connects an approved Canvas institution once. Wrytely discovers accessible
courses, reads syllabi, assignments and discussions, records provenance, monitors
changes while the student is absent, and offers to own a concrete commitment.
The student separately authorizes private work. Monitoring permission is not
drafting, sharing, posting, submission or instructor approval.

Murtazo owns provider adapter, HTTP/OAuth assembly, connection/status/course UI,
ingestion orchestration and their tests. Akbar owns shared credential/state/sync
storage contracts and migrations, discovery/commitment/offer persistence, planner
and runtime control. Reuse SourceObservation, Store.observe_source, current agent
identity, private snapshots/results and atomic private-duty setup. The proposed
shared operations below must be agreed before dependent implementation; they do
not exist yet. No second agent runtime, database client or notification service.

## Access decision and first blocker check

Required answers from Akbar/operator, without secret values:

- Institution's exact approved HTTPS Canvas origin and whether its administrator
  can enable a scoped OAuth developer key for the existing Wrytely development app.
- Registered callback origin/path, existing secret-storage service and operator.
- Consenting student/test course/discussion scope and institutional permission to
  read discussion participant content; no classmates are contacted automatically.
- Whether required syllabus material is HTML, a Canvas page/file or an external
  link, and which institution exposes the actual acceptance example.
- Approved request rate/monitoring interval and model budget for discovery/offers.
  Existing bounded Meta diagnostic approval does not authorize Canvas access.

Canvas OAuth keys/scopes are institution-admin controlled. The app requests an
explicit read-scope subset, not a generic all-access token. User authorization
binds Canvas identity returned by OAuth to the verified Clerk account; browser
owner/course IDs cannot establish that mapping. Tokens, refresh tokens and OAuth
codes stay server-side, encrypted through the agreed existing secret service,
never in source observations, model prompts, browser storage, logs or issues.
[Official OAuth](https://canvas.instructure.com/doc/api/file.oauth.html) and
[developer-key scopes](https://canvas.instructure.com/doc/api/file.developer_keys.html).

If an administrator/key or consenting course is unavailable, record **Canvas
access blocked** with the responsible operator and next action. Mock/paste tests
can proceed independently but cannot close the live connector gate. No personal
access-token workaround is silently substituted for the approved OAuth product.

## Proposed read surface

Scopes use the official `url:GET|` prefix plus the documented route template.
Course IDs originate from the authenticated provider's course discovery result.

| Purpose              | Initial endpoint                                                                       | Evidence/limit                                                                                     |
| -------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Course discovery     | GET /api/v1/courses, student enrollment filter, include syllabus_body                  | Follow all pages; record actual course IDs/name/time zone, accessible syllabus HTML                |
| Assignment discovery | GET /api/v1/courses/:course_id/assignments                                             | Follow all pages; retain effective dates, description and accessible rubric context                |
| Assignment detail    | GET /api/v1/courses/:course_id/assignments/:id                                         | Reconcile changed bodies/dates; use current student's view, never infer another student's override |
| Discussion discovery | GET /api/v1/courses/:course_id/discussion_topics                                       | Topic descriptions alone do not mean all entries/replies were read                                 |
| Discussion messages  | GET /api/v1/courses/:course_id/discussion_topics/:topic_id/view, include_new_entries=1 | Merge/deduplicate threaded and newer entries; record incomplete/unavailable views honestly         |

This is a proposed minimal surface, not a claim these scopes are enabled. The
OAuth token response supplies the Canvas user identity. Group-specific discussions
need their separately approved group-discovery/read scope when the actual course
uses them; course endpoints must not be claimed to cover inaccessible groups.
Canvas's discussion view can require an initial post or temporarily be unavailable.
Never post to unlock it: show restricted coverage and the actual access blocker.
Syllabus links/attachments require a separately reviewed allowlisted file/page
reader if necessary for the real syllabus. A link-only response is not read content.
[Courses](https://canvas.instructure.com/doc/api/courses.html),
[assignments](https://canvas.instructure.com/doc/api/assignments.html),
[discussions](https://canvas.instructure.com/doc/api/discussion_topics.html),
[OAuth token fields](https://canvas.instructure.com/doc/api/file.oauth_endpoints.html).

## Monitoring and evidence correctness

Proposed initial target: one sync due every five minutes per connected account,
subject to owner-approved API budget, persistent bounded batches and backoff. This
is a polling target, not realtime delivery. A durable scheduler resumes saved
cursors while the student is logged out; the browser is never the polling owner.
Use one active sync claim per connection and fair bounded batches across accounts.

Follow opaque next-page Link headers after validating the same approved HTTPS
origin/path; send Authorization only to that origin and refuse redirects. Use
bounded timeouts, body/page/item limits, cancellation and exponential backoff with
jitter. Honor documented throttling and Retry-After when present. A truncated,
failed or still-paginated scan is partial and resumes later; it is not an empty
course or a completed scan. Do not infer deletion from a missing item on one page,
an access failure or a partial scan. Reconcile retained courses that still have
active duties rather than silently abandoning them after enrollment changes.
[Pagination](https://canvas.instructure.com/doc/api/file.pagination.html) and
[throttling](https://canvas.instructure.com/doc/api/file.throttling.html).

Canonical source identity includes connection namespace, provider course ID,
resource kind and stable provider object/entry ID. Version identity combines
provider revision metadata with a digest of normalized relevant content/dates;
retrieval time alone must not create a new version. Convert HTML to deterministic
plain text, preserve exact quotations of that saved representation and safe
provider references. Do not execute HTML or fetch arbitrary embedded links.
Content above the existing24,000-character bound needs agreed stable segmentation
and coverage metadata; never silently truncate it or invent whole-source coverage.

An unchanged successful read must record separate last_checked freshness without
rewriting the immutable source version's original retrieval time. Current
observe_source replays preserve that original time, while drafting freshness gates
use it: a shared trusted freshness contract is therefore a real dependency, not a
timestamp workaround. Older/in-flight scans cannot overwrite newer generations;
commit must fence disconnect, token refresh/rotation and sync revision. Content
changes use existing invalidation, not automatic reuse of prior draft permission.

## Proposed shared boundaries for agreement

Names/payloads here are interface proposals; no browser or model may call these
trusted storage operations directly. Akbar finalizes contracts and migrations.

| Operation                       | Proposed request/response and invariant                                                                                                                                                      |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Begin/consume OAuth state       | Verified Clerk identity/session + approved institution; one-use expiring state bound to exact callback; reject replay, mismatch or identity loss                                             |
| Save/revoke connection          | Verified user, provider identity, encrypted secret handle, granted scopes, expiry; monotonic connection generation; revoke cancels sync/discovery claims                                     |
| Claim Canvas sync               | Worker ID → private connection/generation/lease/secret handle and bounded saved cursors; no browser-supplied owner; one claim wins                                                           |
| Commit Canvas sync batch        | Fenced claim + observations + per-resource coverage/errors/check times + cursor; source versions, change events and checkpoint commit atomically or safely idempotently                      |
| Private connection projection   | Connected/reconnect-needed, institution alias, last attempt/last complete read, next due, discovered-course counts or unknown, per-course/resource coverage and controlled errors; no tokens |
| Queue discovery/ownership offer | Newly committed source version IDs + verified account/generation; deduplicate on provider commitment/revision; durable offered/accepted/declined/superseded states                           |
| Accept work offer               | Verified student + offer ID + explicit private scope/idempotency key; atomically use current evidence through existing trusted delegation boundary; never authorize from source text         |

Model-backed discovery is queued only for new/changed relevant evidence, within
approved usage limits. The runtime cites assignment/discussion evidence for owner,
deadline and requested work; uncertainty becomes a question rather than invented
responsibility. Offer presentation reuses the existing decision area, not a second
chat app. No duplicated offers after polling/restart; declined work is not offered
again merely because it was re-read unchanged. Changed requirements need the
owner-agreed reassessment/reauthorization policy; do not silently revive parked A4.

Controlled errors: authentication revoked/expired → reconnect needed; forbidden or
initial-post-required → restricted coverage;429/5xx/timeouts → retry-later with last
successful evidence labeled historical; invalid/paginated/oversize → partial.
No empty-success fallback, raw provider text or secret data in public responses.
Disconnect immediately fences reads/commits/offers; historical private evidence
retention/deletion follows an explicitly agreed product policy, still unresolved.

## Implementation slices and acceptance gates

1. Agree access, secret/sync/freshness/offer contracts and exact ownership first.
2. Implement OAuth/status + adapter tests against mocked paginated/error responses;
   no live grant inferred. Prove account isolation, state replay rejection,
   redirect/cross-host rejection, refresh/disconnect races and complete/partial labels.
3. Wire persisted monitoring and change ingestion through delivered shared methods;
   prove restart continuation, unchanged-read dedup, changed/deleted/access-lost
   handling and freshness without rewriting version history.
4. Connect runtime discovery to a cited proactive offer and explicit student
   acceptance, then existing private checked work. No blanket source authorization.
5. With separately approved institutional grant/read/model scope, connect a real
   consenting Canvas account, discover courses without manual IDs, read the actual
   syllabus/assignment/discussion, leave the student absent, observe a new/changed
   item and one deduplicated offer, accept it and inspect autonomous private results.
   Demonstrate disconnect and second-account isolation. Record restrictions; do
   not mark the whole gate passed if required material was inaccessible.

Current result: proposal only. Source/app implementation awaits owner agreement
and live access approval. The Meta404/M1 business-lock issues remain separate;
Canvas observation does not bypass either provider or delivery gate.
