# Canvas retrieval and document segments — v1 proposal

Issue [#77](https://github.com/Akbarhoja/wrytely-agent/issues/77). Owner A designs
shared storage/read contracts; M reviews consumers and implements provider, extension,
HTTP and UI assembly. **Proposed, not agreed or executable.** This expands the
[C3 proposal](AGENT-ACTIONS-v1.md#c3--private-retrieval-and-semester-context) and
[#4 discussion](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6539360306).
Existing C1/C2 v1 stays unchanged. No migration, reader, document upload or source
activation is supplied by this document. M must agree the exact revision before coding.

## 1. Identity and access

Verified-user reads derive the agent from the authenticated session. Lease reads
first fence the existing task lease and derive its agent; a model never supplies
user_id, agent_id, provider_subject, a credential or an arbitrary URL. All joins
include the derived agent, connection, current subject, course and object identity.
A UUID alone does not authorize a read. No body is returned across accounts.

For body reads the connection must be connected, the course and resource selected,
and the observation in the current connection generation. Disconnect/reconnect,
account switch, pause for a task reader, or scope removal fences the next read.
Returning a page is not permission to keep using it after a control change; final
work/action checks revalidate all referenced evidence and control generations.
Disconnected private history is deferred to a separately agreed retention/read API.

A historical observation in the _current_ generation may be explicitly inspected
for comparison, but must be labeled historical and unusable for current decisions.
An explicit version/observation miss never falls back to a different current version.
Client-supplied observation times remain claims, not proof of provider truth.

## 2. C3 first read operations

Proposed Store methods, not HTTP route names:

```text
list_canvas_evidence(verified_user, *, connection_id, course_id=None,
                     limit=20, cursor=None)
read_canvas_evidence(verified_user, object_id, *, observation_id=None,
                     offset=0, limit=12000)
list_canvas_evidence_for_task(lease, *, connection_id, course_id=None,
                              limit=20, cursor=None)
read_canvas_evidence_for_task(lease, object_id, *, observation_id=None,
                              offset=0, limit=12000)
```

Task methods use the same implementation after fencing, restricted to that task's
bound course/source scope. They do not expose every source owned by the student
merely because a task exists. A future semester-supervisor scope needs a separate
server-owned capability; these methods do not create one.

List validates connection ownership and optional canonical numeric course ID;
limit is an integer 1–50, never bool. Return `{sources, next_cursor}` ordered by
object UUID ascending. Cursors are opaque, tamper-evident and bound to agent,
connection, generation and filter, expiring after 15 minutes. No total count is
required. The private projection for each item contains exactly:

```text
object_id, source_id(nullable), connection_id, course_id, kind, provider_id,
title, latest_version_id(nullable), latest_observation_id,
document_version_id(nullable), coverage, resource_coverage,
missing_pending_confirmation, historical, freshness
```

`latest_version_id` refers only to an actual text source version; a document root
uses the separate `document_version_id`. Do not manufacture a text version for a
manifest or empty/restricted text. List omits body, payload fields, references,
private provider cursors, subject and all credentials. List may show owned metadata
from a disconnected connection, labeled unavailable; it does not grant body access.

Read resolves the latest observation unless an exact owned observation_id is given.
Return the list identity fields plus `observation_id, version_id(nullable),
observed_at, received_at, provider_updated_at(nullable), reference, fields, missing,
section`. `fields` is only the exact resource-specific allowlisted payload, not a
provider response. `reference` is a server-derived inert label
`canvas-object:<course_id>:<kind>:<provider_id>`, not a stored arbitrary provider URL.
Raw/signed URLs and credentials are not returned. A later canonical clickable provider
link requires a reviewed M mapping from the configured origin and validated IDs.
Restricted/unsupported observations may have empty text and null version_id.

For current short text, `section` is `{text, offset, next_offset, total_characters}`.
Offset is a nonnegative integer, limit 1–12000, maximum total response JSON 1 MiB.
Offsets count Unicode code points in immutable NFC/newline-normalized stored text,
not UTF-8 bytes or JavaScript UTF-16 units. Offset beyond length is invalid; exactly
at the end returns empty text and null next_offset. A nonzero offset requires an
explicit observation_id, so a continuation cannot silently switch versions. The
response repeats its observation/version identity on every page. Changing current
content between requests does not make old content current.

Document reads retain the same ownership checks but return `section=null` and an
ordered `document` descriptor with root version, manifest and coverage; use section
operations below. A short-text read never returns the first 12,000 characters as
though they were a whole document.

Freshness contains exactly `{usable, reason, checked_at, expires_at}`; timestamps
are aware ISO strings or null. Server code chooses inspection purpose. Use the
unwired policy documented in [CONTRACTS](../../CONTRACTS.md#p1-a2-internal-freshness-increment--issue-73)
after deriving current generation/scope/item/resource coverage from owned DB state.
Do not choose an older complete observation when the latest is partial or restricted.
Use the latest authoritative resource attempt, including a failed newer attempt;
an old complete scan cannot conceal a current gap. Replays do not advance check age.
An observation predating a generation change requires a new check, even if text matches.

Invalid bounds/cursors -> ValueError (M maps to controlled 400). Nonowned/missing
connection, course, object or observation -> LookupError (same generic 404).
Owned but disconnected/generation-changed/unselected body reads -> a controlled
`source_refresh_required` conflict (409); include no text. Task lease loss retains
LeaseLost. Do not return raw DB/provider exceptions. Authenticated responses are
private/no-store, including errors. Stale/partial _accessible_ text can be inspected
with `usable=false`; that flag cannot be overridden by a model argument.

## 3. Document identity, parts and manifest

Document support requires an additive, separately reviewed schema and C2 extension.
Current v1 academic batches reject document fields; do not overload content with a
truncated file or silently extend an exact-fields v1 payload.

Stable document identity is the same scoped owner object: connection + subject
namespace + course + object kind + provider ID. An assignment's long body belongs
to that assignment; a file is its own file object. References from an assignment or
syllabus to a file are explicit links, not permission to copy another course's file.
Modules/file relationships and effective assignment dates still need provider mapping.

One immutable document version consists of metadata and an ordered slot manifest.
Root metadata: `title, format(text|html_text|pdf_text), extractor_version,
provider_updated_at(nullable), total_pages(nullable), total_characters, coverage,
missing`. `extractor_version` is a controlled adapter version, not source instructions.
Title is at most300 code points; extractor_version is a controlled ASCII identifier
of1–64 characters; missing has at most50 controlled codes of1–256 characters each.
provider_updated_at uses existing strict aware RFC3339 validation or null. Integer
fields reject booleans. PDF format requires total_pages1–200; other formats use null.
Hex hashes are exactly64 lowercase hexadecimal characters; IDs are canonical UUIDs.
Unknown metadata/slot/part keys are rejected, not copied into stored provider payloads.

Manifest slots contain exactly:

```text
slot (zero-based integer), start, end, page(nullable), text_sha256
```

Each slot has nonempty normalized text, at most24,000 code points. start/end are
half-open global code-point offsets; slots cover [0,total_characters) contiguously,
without overlap or gaps. Split _after_ whole-text normalization; concatenation must
remain NFC. At most512 slots and200,000 total text characters. PDF page provenance
is positive, nondecreasing and within total_pages (maximum200); use null for non-PDF.
Missing/image-only pages appear in explicit missing coverage; do not invent empty
text slots. A zero-text restricted/unsupported document can have an empty manifest,
zero characters and no fake source text version. Nonempty evidence remains partial
when extraction/linked images/layout or unread pages create gaps.

The server recomputes each slot's SHA256 from its exact UTF-8 text. Root digest uses
the existing canonical-source v1 encoding with kind=document, content="", and fields
containing format, extractor_version, total_pages, total_characters and ordered slots;
title/coverage/missing retain their canonical payload positions. References and check
times stay observation provenance, outside content identity. Do not compare an
unverified client digest and mark the upload complete. New cross-language digest
vectors must be agreed and tested before a collector generates these payloads.

Server-issued root/segment UUIDs are opaque, owner-bound IDs. Root versions are not
legacy source_versions with empty bodies. Identical document content can reuse a
root version while recording a new check; A→B→A retains the transition observations.
Replacing a reference or check time alone does not change immutable document text.

## 4. Proposed upload lifecycle, separate from current v1 commits

Proposed Store operations use the existing ingestion credential and scan lease:

```text
begin_canvas_document(credential, origin, *, scan_id, lease_token,
                      request_key, resource, owner_object, metadata, manifest)
put_canvas_document_parts(credential, origin, *, scan_id, lease_token,
                          upload_id, request_key, parts)
finish_canvas_document(credential, origin, *, scan_id, lease_token,
                       upload_id, request_key)
```

These names/payloads require M agreement; no corresponding HTTP route exists.
`resource={course_id,kind}` and `owner_object={kind,provider_id}` must match the
current selected scan resource. An assignment body cannot be uploaded under files
or rebound to another course/subject. Metadata/manifest follow section3 exactly;
request_key follows the existing bounded replay-key syntax. Begin returns
`{upload_id,expires_at,received_slots:[]}`. Expiry is the earlier of scan expiry and
30 minutes; these operations never renew the scan lease or credential.

Parts are `{slot,text}` records; at most50 per request, 1 MiB actual JSON bytes,
with strict duplicate/unknown-field rejection. Put verifies supplied text against
the manifest and returns `{upload_id,received_slots}` with sorted slot indices.
Retrying the same operation/key/payload returns its original durable receipt; changed
payload/key reuse conflicts. A slot cannot acquire different text under another key.
Replay never refreshes observations or ages. Out-of-order arrivals are allowed;
manifest order, not arrival order, determines reading order.

Finish requires all slots, matching hashes/lengths, normalized concatenation and
valid page/coverage metadata. It returns `{upload_id,document_version_id,ready:true}`
for a _staged_ root only. No current object pointer, check time, event, resource
coverage or scan checkpoint changes at finish. An interrupted upload remains staged
and is invisible to readers; missing slots cannot become complete by timeout.

A subsequent **proposed C2 schema_version2 document batch** references the finished
upload ID for its matching owner object. It retains the existing C2 envelope,
resource/checkpoint/coverage, replay and lease rules; document items contain only
`kind, provider_id, provider_updated_at, title, reference, upload_id` rather than
inline content. The server derives coverage/fields/text identity from its finished
upload; item metadata must equal the staged header. No change to schema_version1.
The batch's single transaction publishes root/observation pointers, records the check
and content/coverage events, and advances the checkpoint/receipt together. Mixed
inline/document items and exact schema2 discriminators require follow-up agreement;
the initial document-only variant must reject inline items, not guess their shape.

Disconnect, subject/scope/generation change and expired scan/upload reject writes
and publication. Resume may use a newly fenced lease for the same active scan;
an old lease can never commit. Resource completion cannot certify full coverage
while a referenced document is incomplete. Pending uploads do not hide old evidence
as current; a failed latest attempt remains a visible coverage gap. Retention and
bounded cleanup of orphaned uploads need an explicit reviewed implementation.

## 5. Original-section reading and citations

Proposed `read_canvas_document_sections(verified_user, object_id, *, observation_id,
document_version_id, first_slot=0, limit=10)` and the identical `_for_task(lease,...)`
variant require nonnegative integer first_slot and return `{object_id, observation_id, document_version_id, sections,
next_slot, total_slots, coverage, missing, historical, freshness}`. Each section
contains `{segment_id,slot,start,end,page,text,text_sha256}`. Limit1–20, maximum
40,000 total code points; append whole slots until the next would exceed the cap,
then return its slot as next_slot. One slot is at most24,000, so progress is possible.
All IDs must belong to the same owned root and observation; never mix document
versions between calls. first_slot beyond total_slots is invalid; at the end returns
an empty list/null next_slot. No current-version fallback for an explicit old root.

Citations include root version, segment ID, page/offsets and an exact quote. Final
verification resolves those references within the same current owned document,
rechecks coverage/freshness, and verifies quote containment. A partial extraction
cannot prove absence of policy or completeness of a rubric. Model summaries are
indexes for investigation, not substitutes for original source sections.

Synthetic slot example (digest omitted here; a collector must supply the actual hash):

```json
{
  "slot": 0,
  "start": 0,
  "end": 13,
  "page": 1,
  "text": "Project brief"
}
```

Unicode continuation example for immutable text `A📚B` (three code points). The
caller pins observation_id; a page beginning at offset1 returns the two remaining
code points even though the emoji occupies two JavaScript UTF-16 units:

```json
{
  "text": "📚B",
  "offset": 1,
  "next_offset": null,
  "total_characters": 3
}
```

## 6. Implementation order and acceptance gates

1. M agrees/refines this design, PDF execution boundary and required collector fixtures.
   Record exact accepted revision; proposed names are not executable methods.
2. A implements bounded owned C3 reads for the existing staged short-text schema;
   test current/partial/history, paging/version drift, resource failure, disconnect,
   stale generation and cross-account denial. No legacy source promotion.
3. A implements additive document storage/upload/publication and digest vectors;
   M implements the agreed document-only C2 assembly and extractor independently.
   Review replay, missing/changed slots, limits, malformed Unicode, lease/scope races,
   A→B→A, crash before publication and transaction rollback.
4. A adds bounded section reads and citation verification; M adds exact API/extension
   consumers. Validate long sources across multiple pages, emoji/code-point offsets,
   images/unread gaps and original-section citations without silent truncation.
5. Integrate reviewed heads and run synthetic two-account workflows; separately prove
   consenting Canvas file collection and provider limits. Activate model source
   consumers only after freshness/readiness and current permission checks agree.

P1-A2 and the full autonomous agent remain unfinished until their complete work-order
checks pass. This proposal does not remove P0 live gates, approve spend, deploy a
worker, grant provider access or change student-facing legal/retention policy.
