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

The browser package includes the journal/producer import closure. Automatic host
collection still uses the earlier assignment collector; these new methods consume
already-extracted input. No claim of full automatic Canvas collection follows.

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
