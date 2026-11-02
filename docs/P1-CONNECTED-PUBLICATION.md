# Connected P1 document publication and private reads

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
