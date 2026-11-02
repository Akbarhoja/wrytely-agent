# Canvas document-only wire v2 — review candidate

November2 discussion-reply amendment: resource discussions now accepts owner kinds
discussion and entry. Entry uses the existing EvidenceItem entry field set, including
topic_id and parent_entry_id; all other resource/owner combinations remain exact.
No discriminator, staging/replay/authority semantics, schema1 shape or database
schema changes. [Durable entry/reply collection](../P1-CONNECTED-PUBLICATION.md#durable-discussion-entries-and-replies).

November2 status amendment on the same P1 branch: schema2 additionally accepts
submissions/submission and grades/grade, using their existing EvidenceItem fields.
The collector creates explicit selected-field JSON projections with trusted
canvas.json.v1 formatting, partial coverage and uncollected-body/policy/total gaps.
No new HTTP extraction route or database schema is added. The configured trusted
extractor list must include the formatter for staging; defaults remain off.
[Status/grade collection](../P1-CONNECTED-PUBLICATION.md#read-only-submission-status-and-assignment-grades).

November2 implementation amendment under Akbar's P1 reassignment: schema2 now also
accepts announcements/announcement and discussions/discussion, using their existing
EvidenceItem field sets/canonicalization. This is an additive pair extension, not
mixed inline/document publication. All original pairs, discriminator, authority,
bounded staging, digest and replay semantics remain. HTTP extraction/collector
support is implemented on codex/p1-completion; discussion replies remain unread and
explicitly partial. [Connected implementation](../P1-CONNECTED-PUBLICATION.md).
This supersedes the four-pair-only scope and old preimplementation ownership wording
below; the historical vectors remain unchanged and continue to apply.

Owner A; consumer reviewer M. Tracks [#77](https://github.com/Akbarhoja/wrytely-agent/issues/77)
and the [explicit follow-up gate](https://github.com/Akbarhoja/wrytely-agent/pull/78#issuecomment-6551693307).
**Proposed, not agreed, implemented, deployed or permission to upload.**
Completes the deferred wire details of [the accepted document architecture](CANVAS-RETRIEVAL-SEGMENTS-v1.md#3-document-identity-parts-and-manifest).
Current schema1, short-text readers and M's assignment collector remain unchanged.
M must agree this exact revision and vectors before dependent implementation.

## 1. Exact discriminator and authority

For **C2 publication batches and their receipts** (§4), the discriminator is the
pair `schema_version:2, batch_type:"canvas_documents"`. Both keys are mandatory,
with integer2 (not bool/string) and the exact literal. Integer2 alone never selects
the publication parser. Publication shapes forbid the staging `operation` key and
mixed inline/document items; unknown fields reject the whole operation.

**Staged begin/put/finish requests and receipts** (§2) instead use the exact pair
`schema_version:2, operation:"begin_document"|"put_document_parts"|"finish_document"`.
Their exact shapes deliberately contain NO batch_type; supplying it is an unknown-key
error. The trusted assembly dispatches by the operation-specific staging endpoint or
the publication endpoint, never by schema_version alone or payload-shape guessing.
An operation cannot be interpreted as a publication batch, or vice versa. No schema1
item acquires optional document fields.

All operations use the existing verified ingestion bearer, operator-approved origin,
connection generation, current subject and selected course/resource/scan. Bodies
never supply authoritative agent/user IDs. Existing credential and lease fencing,
scan expiry, rate/size bounds and controlled private errors still apply. Public
HTTP route names/transport assembly remain M-owned and require agreement; the
internal operation names below are not claims that endpoints exist.

## 2. Staged upload requests and receipts

Every staged request body has exactly the fields shown here (types after colons).
The §1 publication batch_type requirement does not apply to these staging bodies:

```text
common = schema_version:2, connection_id:UUID, generation:int>=1,
         scan_id:UUID, subject:string, lease_token:opaque, request_key:replay_key
begin = common + operation:"begin_document", resource:{course_id,kind},
        owner_object:{kind,provider_id}, object_fields:object,
        metadata:{title,format,extractor_version,provider_updated_at,total_pages,
                  total_characters,coverage,missing}, manifest:[slot...]
put   = common + operation:"put_document_parts", upload_id:UUID,
        parts:[{slot:int,text:string}...]
finish= common + operation:"finish_document", upload_id:UUID
```

`resource.kind`/`owner_object.kind` pairs initially allowed: assignments/assignment,
syllabus/syllabus, pages/page, files/file. Other academic kinds remain schema1;
a later separately reviewed extension is required for their long bodies. This is
an implementation sequence, not removal of the complete product's source kinds.
Course IDs, provider IDs, replay keys, timestamps and UUIDs retain existing strict
validators. Owner object is bound at begin and cannot change at put/finish/publication.

Assignment/syllabus/page `object_fields` are exactly their existing schema1 field
sets and canonical validation from `contracts/canvas_evidence.py`. No loss of dates,
rubric or structured assignment fields when a body becomes a document. File fields
are exactly `{filename,content_type}`: filename1–300 normalized code points, no path
separators/NUL; MIME one of application/pdf, text/plain, text/html. Both fields are
required. File's provider_id is the numeric Canvas file ID; selection still requires
files to be in the scan. Reading a link never authorizes another course's file.

Metadata and slots retain the bounds of architecture section3:512 slots,200000
code points,24000/slot,200 PDF pages; title300, extractor identifier64, missing50.
Missing codes use `[a-z0-9][a-z0-9_.:-]{0,127}`. Integers reject bool. Complete requires
nonblank title/text and no missing codes. Empty restricted/unsupported/partial roots
have zero slots/characters and retain the gap; they cannot certify completion.
Formats are text/html_text/pdf_text; PDF requires pages1–200, others total_pages=null.
Extractor identifiers must be in server configuration; source text cannot choose code.

Normalize whole logical text to LF then NFC before segmentation. Reject lone
surrogates, invalid page provenance, gaps/overlap and concatenation that is not NFC.
A PDF extractor preserves page boundaries. For these wire vectors, nonempty extracted
pages are joined with one LF; that separator belongs to the following page's first
slot. Empty/unread pages contribute no invented text and appear in missing codes.
Reject a manifest if its offsets/slot text do not reconstruct the agreed normalized
whole text. Offsets count code points, never UTF-16 units or UTF-8 bytes.

Begin/put/finish use at most1MiB UTF-8 JSON each. Put accepts1–50 unique slots;
zero-slot documents skip put. No raw file bytes, download URLs, provider token or
cookie enters this interface. Raw provider fetching and process-limited extraction
remain M's adapters and the separately agreed PDF boundary.

Exact response shapes:

```text
begin: {schema_version:2,operation:"begin_document",receipt_id:UUID,
        upload_id:UUID,expires_at:aware_timestamp,received_slots:[],replayed:bool}
put:   {schema_version:2,operation:"put_document_parts",receipt_id:UUID,
        upload_id:UUID,expires_at:aware_timestamp,received_slots:[int...],replayed:bool}
finish:{schema_version:2,operation:"finish_document",receipt_id:UUID,
        upload_id:UUID,document_version_id:UUID,document_digest:sha256,
        ready:true,expires_at:aware_timestamp,replayed:bool}
```

received_slots is the sorted cumulative set as of that operation's original commit,
not a mutable progress query. Expiry is min(scan expiry, begin time+30min), never
extended by replay/resume/put. A ready root is still staged, not visible evidence.
Every operation/key has a canonical payload digest scoped to upload/scan/operation;
lease_token is authorization, excluded from immutable replay identity. Reusing a key
with changed payload conflicts; identical retries return the original receipt with
only replayed=true. Replaying an old receipt never grants a new lease or advances
freshness. Validate current credential/generation/lease/scope/expiry before returning
receipts; a revoked credential cannot recover one. Repeated slot with identical text
is idempotent; changed text is a conflict even under a different request key.

## 3. Canonical roots and fixture agreement

Each slot is exactly `{slot,start,end,page,text_sha256}`. Hash exact normalized slot
text UTF-8 with SHA256. Server recomputes all hashes/lengths at finish; client hashes
are claims. Parts cannot change the manifest. Document root uses the existing
`canonical_source_bytes` algorithm with exactly this payload:

```text
{digest_version:1,kind:"document",title:metadata.title,content:"",
 fields:{format,extractor_version,total_pages,total_characters,slots,
         owner_kind,object_fields},
 coverage:metadata.coverage,missing:metadata.missing}
```

`slots` is the ordered manifest. `owner_kind` and canonical `object_fields` bind the
structured academic information to this revision. This explicitly supplements the
older architecture's shorter root-field list; it prevents a deadline/rubric change
from being ignored when long-body text stays unchanged. Collection times, subject,
origin, course/provider identity, reference, upload ID and provider_updated_at remain
outside the root hash; object identity remains a separate owned namespace. Coverage
and missing remain content identity under the existing v1 digest rule.

[Fixed synthetic vectors](../../tests/fixtures/canvas_document_v2.json) contain raw
text/page input, normalized text, slots/parts, exact digest payload, canonical UTF-8
and SHA256. Separate wire_cases pin staged/publication discriminators and unknown-key
rejections; they do not alter the ten root-digest vectors. Cases cover NFC/CRLF/emoji, PDF page boundaries, partial/image-page gaps,
zero text and A→B→A. Equal normalized Unicode variants hash equally; changing a page
boundary, structured field or coverage must change the root. A→B→A reuses the first
immutable root but creates three transition observations; do not reuse the first
observation or its check time. Fixtures are review candidates until M's existing
JavaScript canonical helpers pass them and both owners record agreement.

## 4. Document-only C2 publication

The commit_sync_batch call keeps its existing trusted actor, scan_id, generation,
lease_token, batch_key and expected_checkpoint arguments. Its envelope has exactly:

```text
{schema_version:2,batch_type:"canvas_documents",connection_id,generation,scan_id,
 batch_key,subject,resource:{course_id,kind},observed_at,
 items:[{kind,provider_id,provider_updated_at,title,reference,upload_id}],
 coverage:{state,reason,seen_count},next_cursor}
```

Use the existing C2 bounds (items0–50,1MiB, provider cursors4000, cumulative seen_count,
observation window and page/sequence caps). Empty pages are allowed. No inline content,
fields, digest or caller coverage in an item; the server derives them from the ready
upload. Upload is for this exact owner/scan/resource/generation and not expired.
Item title/provider_updated_at must match its staged header; reference is bounded
provenance, never fetched/executable. Reject duplicate kind/provider IDs, reused uploads
under another object and unknown keys. Preserve existing canonical resource-kind rules.

One transaction publishes/reuses immutable roots, creates observations, records resource
checks/events, advances checkpoint and saves the receipt. No partial publication on
missing upload, malformed item or scope race. A root digest alone cannot locate another
owner's root. Global deduplication/body access across students is excluded.

Exact receipt:

```text
{schema_version:2,batch_type:"canvas_documents",receipt_id,scan_id,batch_key,
 batch_digest,checkpoint,coverage,replayed,observations:[
   {provider_id,kind,object_id,observation_id,document_version_id,
    document_digest,coverage,historical}
 ]}
```

UUID fields are server issued; coverage is the existing state literal, historical bool.
No legacy source_versions entry/empty text version is manufactured. batch_digest uses
existing `_hash([expected_checkpoint,envelope])` canonical JSON algorithm; schema2 and
batch_type participate. This operation shares existing batch receipt namespace: reusing
a schema1 key for schema2 conflicts. Resource finalization retains the existing receipt
shape; its manifest digest is SHA256 of canonical sorted JSON rows
`{kind,provider_id,content_digest:document_digest}` ordered by kind/provider_id, in the existing resource
namespace. The document-only resource may not mix inline observations in one scan.
A failed/partial latest resource attempt cannot fall back to older complete proof.

Finish resource still cannot claim complete with partial/historical/missing evidence,
unfinished pagination or mismatching manifest. Source readiness/model activation are
separate later gates, not implied by publication. Cancellation after a committed
publication does not rewrite history; current generation/selection fences further use.

## 5. Errors, quotas and orphan cleanup

Malformed exact keys/types/bounds -> controlled400; unavailable/nonowned upload ->
generic404 with no body; expired/changed scope/checkpoint/unfinished/changed replay ->
controlled409 (codes document_expired, document_not_ready, document_conflict or the
existing scan conflict); upload quota -> controlled429 with bounded retry hint.
Credential/lease failures retain existing mappings. No provider/DB traceback or signed
URL in responses. M's assembly supplies private/no-store responses, including failures.

At most4 unpublished active uploads/connection and8MiB actual staged UTF-8 text per
connection. Enforce counters under the same transaction/connection lock, including
concurrent requests. Reject quota excess before storing parts; it does not delete
published content. An explicit abandoned upload remains bounded by expiry; no automatic
renewal or hidden rescan. Expired uploads cannot publish even if their bytes remain.

Proposed internal maintenance, not public API: one invocation processes at most100
expired uploads or100 unreferenced staged roots, locks candidates with SKIP LOCKED,
and skips rows still in a live publication/lease transaction. Expired upload parts can
be removed after expiry; retain receipt tombstones for the scan receipt lifetime
until a separate safe receipt-retention policy is agreed. Tombstones never retain text.
Unreferenced staged roots may be removed only after24h and after a transactional
anti-join against ALL observations, publication bindings and active nonexpired uploads.
Every observation reference, including historical A→B→A, protects its root/segments.
Foreign keys and locking must prevent a publication/cleanup race. A timed-out upload
is not permission to delete a referenced root. Each pass is bounded; a backlog never
relaxes quotas. Published-content deletion/retention stays a separate user/legal policy.

## 6. Handoff and acceptance

A implements shared validators, additive next-unused migration and staged publication
only after exact agreement; M implements HTTP/extractor/extension consumption under
his own claim. Existing schema1 tests/payloads remain byte compatible. Both owners must
check vectors, lost-ack/changed-key replay, lease rotation, generation/account/course
fences, partial/zero-text, expiry/quota and cleanup/publication races. Python/Node fixture
agreement is necessary but is not live upload, Linux PDF enforcement or agent readiness.

The proposal deliberately leaves no implicit mixed schema2 variant. New routes,
retained migration, continuous cleanup worker, deployment, live source upload and model
activation each retain their existing review/operating gates. No production code or
student data is added by this document.
