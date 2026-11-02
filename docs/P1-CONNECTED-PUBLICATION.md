# Connected P1 document publication and private reads

Latest November2 continuation adds paginated discussion entries and replies as
separate immutable documents. It supersedes older prompt-only scope notes below;
known extraction/attachment/role/date gaps and live acceptance remain unfinished.

November2 continuation adds announcement and discussion-prompt documents to the
automatic collector. This supersedes the three-kind scope described in the older
checkpoint below; discussion replies are still unfinished. No installed/live
collection, worker activation or deployment is implied.

Akbar/Codex implements the reassigned P1 completion on `codex/p1-completion`,
using Murtazo's existing client, journal, host, package and document producer.
This record supersedes the missing-publication and pending-ownership descriptions
in the older pipeline evidence. P1 remains open.

## Connected behavior

The existing private document API now has `POST
/v1/source-connections/canvas/documents/batch`. Its exact wrapper is
`{scan_id,generation,lease_token,batch_key,expected_checkpoint,envelope}`. The
envelope must have integer `schema_version:2` and
`batch_type:"canvas_documents"`. It calls the existing Store transaction once.
It uses the existing ingestion credential, current scan/scope/identity fences,
1MiB streaming limit, extractor configuration default-off, no-store responses and
redacted errors. The schema1 academic batch route is unchanged.

`commitDocumentPage`, `continueDocumentPage` and `finishDocumentResource` on the
existing pairing client prepare original text/pages, stage documents and publish
them through that HTTP endpoint. The existing discovery journal upgrades to
version3 only when documents are used; legacy journals still load. Each step is
persisted before its request. Lost responses retry the same request key and body;
a resumed lease may replace only the writer token. Receipts must match the saved
document digest, root, slots, observation and checkpoint before advancement.

At most four documents are staged per page because the Store permits four live
unpublished uploads. This is a page size, not a course or assignment cap. Subsequent
pages use the same checkpoint and cumulative count. Parts are sent in batches of
at most50 slots, including a tested512-slot document. Checked-empty pages work.
Pagination progress alone does not become a permanent content gap. An actual
partial document or historical observation still prevents complete coverage.

The browser package includes the journal/producer import closure. The next
implementation on this same branch connects automatic assignment, syllabus and
course-page reading as described below. Other source kinds remain unfinished;
this is not full automatic Canvas coverage.

## Automatic document collection

The host now selects `collectDocumentPage` on the actual pairing client. It
discovers courses through the existing course collector, then reads selected
assignments, syllabus HTML and course pages without manually entered course IDs
or assignment uploads. List pages contain at most four objects; assignment/page
detail endpoints supply original bodies rather than treating a list row as complete.
Assignment detail uses effective dates and retains rubric/constraint mapping through
the existing mapper. The provider behavior follows the official
[Canvas assignment API](https://developerdocs.instructure.com/services/canvas/resources/assignments).

Every course/detail read checks the expected signed-in profile before and after
the request. All reads use exact Canvas origin/path, included browser credentials,
GET, redirect-error and no-store. Pagination reuses the original strict Link parser,
rejects unknown/duplicate query keys and follows opaque page tokens only within
the selected course/resource. Provider credentials never leave the browser.

`POST /v1/source-connections/canvas/documents/extract` now reuses the bounded inert
HTML parser with its full200000-character ceiling, not the earlier24000-character
assignment projection. It accepts at most four selected-course HTML inputs, exact
schema2/operation extract_document and current origin/connection/generation/scope.
The actual trusted implementation `canvas.html.v1` must be enabled by the server's
extractor configuration. Context is rechecked after conversion. This endpoint
stores nothing and runs no model. Scripts/embedded/hidden/linked content and parse
limitations remain explicit partial gaps. Locked bodies are withheld entirely.

Extraction request keys are exactly schema_version, operation, origin, connection_id,
generation, scope_revision, resource and items. Resource is {course_id,kind}, with
kind assignments/syllabus/pages. Items are {provider_id,html}, with html string/null.
Response is {schema_version:2,extractor_version:"canvas.html.v1",resource,items};
each result item has provider_id,text,coverage:"partial",missing. This is conversion
only; document begin/parts/finish/batch retain their existing exact wire formats.

The collector feeds converted originals into the existing producer and durable
upload journal. A suspended worker continues saved document phases or replays the
pending receipt before another source read. Older unfinished schema1 assignment
resources finish on their original collector rather than mixing formats mid-resource.
The host uses the earlier collector only for such compatibility or source kinds
outside the new document path. No second scheduler, store or source journal exists.

Two additional actual-client/loopback-HTTP/Store scenarios exercise automatic
two-course collection over three scans each: ten documents initially; unchanged
second sync reuses roots/events; one changed assignment due date creates one new
root/event. Thirty observations, eleven roots/events and no fake legacy versions
are verified. Instructions exceed24000characters and retain their rubric. The
second scenario loses an accepted publication response and recovers the exact
request. Every tick recreates the client from persisted worker state. Scans finish
partial because known extraction/module/file gaps remain; they never claim fully
up-to-date content.

Validation of this automatic-collection checkpoint:1,599backend tests pass on fresh
disposable Postgres, zero skips/two existing warnings138.08s;481Node tests pass;
Ruff lint/format244files, changed-file Prettier and diff checks pass. Thirteen new
extraction tests plus two real-client loopback scenarios account for the15additional
backend cases;21new Node cases cover reader, collector and actual host selection.
The website has no new code in this checkpoint; its previous120tests/TypeScript
result remains the last evidence. No installed or live collection is claimed.

Files/PDFs and linked document contents, modules, announcements, discussions/replies,
submissions/grades, student coverage/results screens and installed/live validation
remain required P1 work. The three source kinds above do not substitute for them.
The extractor remains default-off; no development server or live browser was enabled.

## Announcements, discussion prompts and resource failures

The existing schema2 document discriminator now accepts two additional exact
resource/owner pairs: announcements/announcement and discussions/discussion.
Their object fields reuse the existing schema1 announcement/discussion validators,
including posted_at and required_initial_post. Existing schema1 routes and all
original document pairs retain their meaning; no database migration is needed.
Header and publication parsers share one resource/owner mapping. Extraction accepts
these additional selected resource kinds through the same default-off trusted
canvas.html.v1 implementation.

Both are collected from the course-scoped discussion_topics list/detail API, using
only_announcements=true for announcements and false for discussions. All four-item
pagination, origin/path/query restrictions, identity checks around each request,
full-body extraction and durable staging/publication rules remain. No recent-only
announcement date window is introduced. API behavior follows the official
[discussion topics documentation](https://developerdocs.instructure.com/services/canvas/resources/discussion_topics)
and [announcement documentation](https://developerdocs.instructure.com/services/canvas/resources/announcements).
The detail's is_announcement must match the requested resource to prevent mixing.

Announcement posted_at is normalized to the same UTC microsecond representation
as the existing server field validator before the immutable document digest is
computed. Invalid dates reject rather than roll over into another day. Author roles
remain unknown rather than inferred from display names. Discussion dates remain
unverified/null until effective assignment-date reading is connected for them.

Discussion prompt reads do not request entries/view endpoints or post anything to
unlock replies. They retain discussion_replies_unread, author_role_not_observed and
student_specific_dates_unverified. If an initial post is required and posts are not
visible, initial_post_required remains explicit. Announcements with unknown/nonzero
reply count retain announcement_replies_unread. These gaps are not complete coverage;
the saved prompt is not proof that replies were collected.

A provider403 on one selected resource now closes only that resource as
restricted/permission_denied, allowing other courses to continue. A404 records
partial/extraction_failed; it is neither deletion evidence nor a fabricated claim
about permissions. Session loss/account changes still stop collection. These gap
closures use the existing journal/replay machinery and never invent empty complete
content or delete earlier source history.

Additional connected scenarios exercise five resource kinds across two automatically
discovered courses over three scans:42observations,15roots/events, unchanged-root
deduplication and one changed due date. A separate403 scenario retains a restricted
course-page resource while collecting the other course and source kinds. Real Store
tests independently cover new topic publication/read/replay, exact resource-kind
pairing, cross-account denial and unselected-topic rejection. New Node checks cover
endpoint selection, hidden replies, unknown role/date gaps, microseconds, malformed
dates, resource-level restriction and session-loss handling. Combined regression:
1,604backend tests pass on fresh disposable Postgres, zero skips and two existing
warnings147.78s;493Node tests pass. Ruff lint/format245files, changed-file Prettier,
documentation links and diff checks pass. Three new Store/HTTP cases and two new
actual-client scenarios add five backend cases; twelve new Node cases add source
and failure-handling coverage. Website code is unchanged from its prior120tests/
TypeScript pass. These are local/synthetic results, not installed/live validation.

Discussion replies, modules, files/PDFs and linked contents, submissions/grades,
student screens and installed/live acceptance remain P1 work.

## Durable discussion entries and replies

The discussions resource now permits both discussion and entry owners in the
existing schema2 document protocol. Entry fields reuse the original EvidenceItem
entry schema: topic_id, parent_entry_id, author_role, required_initial_post and
due_at. Header/publication validation uses the same kind predicate; all other
resource pairs stay exact. No database schema or new endpoint is introduced.

The prompt collector creates a content-free continuation in the original sync
cursor for topics whose posts are explicitly visible and not locked for the user.
It then reads GET discussion_topics/{topic}/entries in four-item pages, followed
by GET discussion_topics/{topic}/entries/{entry}/replies for every top-level entry.
It never treats recent_replies as the whole thread: the official
[discussion API](https://developerdocs.instructure.com/services/canvas/resources/discussion_topics)
documents that those embedded samples include only the ten most recent replies.
Each reply list follows its own validated pagination until exhausted.

The wrytely-discussion-v1 cursor stores only version, selected course, up to four
topic IDs, topic-list continuation, phase, entry-list continuation, up to four
pending parent IDs and reply continuation. It is at most4000characters, is private
scan state rather than another journal, and contains no message text. Exact shape,
canonical serialization, IDs and every course/topic/parent endpoint/query are
validated before network access. Cursor continuation cannot change course/origin,
introduce writes or invoke quiz endpoints. Existing batch persistence, replay keys,
leases, scan/generation/subject/scope fences and size/page ceilings remain active.

Before every entry/reply page, the reader refreshes topic detail and rechecks post
visibility. Profile identity checks still wrap every provider request. Hidden or
locked topics are skipped without requesting their entries; a provider403 preserves
the existing restricted-resource behavior. No post is written to unlock content.
Session/account loss remains a stop. Initial-post-required gaps are retained.

Each entry/reply becomes its own document with the original converted message,
stable entry ID, verified request-topic context, and parent entry ID for replies.
The reader overwrites its derived marker and strips it from ordinary prompt data;
provider content cannot forge that internal binding. A conflicting returned parent
rejects. Recent-reply samples are ignored for publication. Author role and effective
dates remain unknown; unread attachments remain explicit gaps. Missing/deleted text
is not fabricated, and a missing entry is not automatically deletion evidence.
Prompt documents remain partial with their separate-thread gap; collected entries
do not silently certify the entire course up to date.

Two new actual-JS/loopback-HTTP/Store scenarios discover two fixture courses and
collect top-level entries plus twelve replies per sampled thread over three scans,
recreating the client each tick. Each scenario verifies120observations/42roots/events,
84entry observations, exact parent links and original texts beyond the first ten
replies. Unchanged scans dedupe; one changed reply plus one changed deadline creates
two new roots/events. The second scenario loses an accepted entry publication and
replays its exact request before continuing. A new Store/HTTP entry-owner case covers
original retrieval/replay/account isolation. Thirteen new Node cases cover cursor
shape/content isolation, visibility, pagination, parent binding and forged markers.

Validation: full fresh disposable backend1,610PASS, zero skips/two existing warnings,
171.52s; all525NodePASS; Ruff lint/format245files, changed-file Prettier, documentation
links and diff pass. Focused nine backend cases pass22.29s. Three backend cases
(two actual-client scenarios and one additional owner-pair case) and thirteen Node
cases are added. Website code is unchanged from its prior120tests/TypeScript pass.

Installed/live collection and sustained browser recovery are separate acceptance;
these are synthetic tests. Modules, files/PDF/linked contents, submission bodies/
feedback, student coverage/results screens and live validation remain P1 work.

## Read-only submission status and assignment grades

The document pipeline now also accepts submissions/submission and grades/grade,
using the existing EvidenceItem field sets. The host reads the course-scoped
students/submissions GET endpoint with include[]=assignment, four items per page.
It omits student_ids so Canvas uses the calling student, then independently checks
every returned user_id against the paired signed-in subject. Included assignment
ID/course must match; missing/mismatched assignment context rejects. Pagination
cannot add student_ids=all or escape into a different course, quiz or attempt path.
The documented read behavior comes from the official
[Canvas submissions API](https://developerdocs.instructure.com/services/canvas/resources/submissions).

Submission projection stores assignment ID, submitted time, workflow state, attempt
number and observed late/missing booleans. Missing flags remain null with explicit
gaps. Grade projection stores the provider's assignment score, points possible,
grading type and grade. A null grade remains unknown; it is never zero or a guessed
course total. grade_basis distinguishes provider_reported_current_attempt,
provider_reported_previous_attempt and provider_reported_attempt_unverified using
Canvas's observed grade_matches_current_submission flag. Missing verification is
not treated as true. Excusal and no-longer-visible-assignment flags remain explicit
gaps, with unknown flags separately marked. No weighted average or pass/fail
inference is introduced.

These are explicit selected-field JSON projections, marked partial, rather than
claims to have read full submissions or feedback. The trusted local formatter is
canvas.json.v1 and must be enabled in server extractor configuration before document
staging; defaults remain off. It reuses the producer, canonical numeric formatter,
durable journal, original-section storage and publication. JSON projection omits
provider user IDs, submission bodies, feedback and uncollected extra fields. It
does not pass JSON through the HTML converter or add another persistence layer.

The synthetic automatic status scenario discovers two courses, collects status and
grade documents, repeats unchanged input, then changes one grade and one assignment
deadline. Original projections stay private and source changes create distinct
roots/events. Additional actual Store/HTTP cases cover these new owner pairs,
source retrieval, replay and account isolation. Node cases verify current-user-only
GETs, no quiz navigation, unknown grades/flags and projection bounds.

Final validation:1,607backend tests pass on fresh disposable Postgres with zero skips
and two existing warnings157.60s;512Node tests pass. Ruff lint/format245files,
changed-file Prettier, documentation links and diff checks pass. Three backend
cases are added (one actual-client scenario and two new Store/HTTP owner pairs),
plus nineteen Node cases. The earlier full run before grade-attempt refinement
passed1,607tests152.50s; the final run includes that refinement. Website code is
unchanged from the prior120tests/TypeScript pass. These results are synthetic/local,
not live collection proof. Submission bodies/feedback, complete course grade basis,
modules, discussion replies, files/linked contents and student screens remain work.

Quiz handling is passive-only as recorded in BUILD-PLAN/WORK-ORDERS. Existing quiz
assignment/status information can be read without starting an attempt. No quiz
start/resume/question/attempt endpoints or provider writes are called. Quiz-specific
time-limit/question support is not claimed by these status reads.

## Private result HTTP

These verified-session GET routes now call the existing private v2 Store methods:

- `/v2/responsibilities/{responsibility_id}/artifacts?limit=20&before=...`
- `/v2/artifacts/{artifact_id}`
- `/v2/artifacts/{artifact_id}/evidence/{group}/{index}?check_id=...&first_slot=0&limit=1`

Only the documented query keys are accepted; repeated query keys reject. The list
encodes `next` as canonical unpadded base64url JSON, at most512bytes; the underlying
cursor contains only created_at/id and grants no access. Other-account ownership
is rechecked on every page. Policy/rubric reads require the saved check ID.
All success, authentication, validation and error responses are no-store. Revoked
sources block embedded draft quotations as well as original-source reads.
SourceRefreshRequired maps to409/source_refresh_required, bounded-read failures
to413, unknown IDs to404, invalid input to400 and unexpected failures to redacted503.
No route retries, mutates work or runs a model. Existing v1 filters are unchanged.

The web proxy now explicitly permits these verified-session GET routes, preserves
only their allowed query keys, rejects duplicates and never forwards browser
authorization/cookies as identity. The student result UI does not yet consume them.
That remains part of this same P1 feature, alongside the missing resource collectors.

## Evidence

- Actual Node client → loopback FastAPI → disposable Store:12 document scenarios
  pass, including recreated clients, accepted-response loss at all four stages,
  lease rotation after lost publication, bad receipts, altered saved input,
  empty/syllabus pages, four-document pages, five documents across two pages,
  and512 slots over11 part requests. Nineteen pre-existing scenarios also remain
  in the combined suite.
- Sixteen additional real-Store publication HTTP cases cover configuration,
  credentials, exact schema/wrapper, changed replay, current controls and a
  committed response loss without an in-request retry.
- Twenty-five real-Store private result HTTP cases cover original evidence,
  session/account isolation, query bounds, pagination ties/cursors, saved check
  selection, disconnection and redacted errors.
- The nine producer-to-checked-draft scenarios now publish through real HTTP,
  replacing their explicit internal Store bridge. Model responses remain scripted.

Full regression:1,584backend cases pass on fresh disposable Postgres with zero skips
and two existing warnings (133.05s);460Node tests and120web tests pass, as do
TypeScript and Ruff lint/format243files. These tests do
not prove installed Chrome behavior, live source extraction, deployed endpoints,
Meta quality, WhatsApp delivery or continuous operation. No provider call, spend,
installation, new consent, retained migration, deployment or main merge occurred.
