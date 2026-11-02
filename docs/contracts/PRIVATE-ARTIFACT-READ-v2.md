# Private document-backed artifact reads — v2 proposal

**Store implemented; HTTP/UI assembly remains M-owned.** Akbar removed the mandatory
agreement gate November 1. A implemented this versioned boundary on
codex/private-artifact-results. M can assemble the concrete methods after code review,
raising actual incompatibilities asynchronously. Original consumer request:
[#152 comment6564664188](https://github.com/Akbarhoja/wrytely-agent/pull/152#issuecomment-6564664188).
Implementation/evidence: [private result reads](../P1-PRIVATE-ARTIFACT-READS.md).

Claim: [6565297576](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6565297576).
Base: #156 `cba20736d8a22f085042f6e86d0d97222a763621`.

The internal DraftArtifactV2 already preserves mixed evidence. Existing v1 list,
detail and status projections deliberately hide evidence_schema2. This proposal
adds explicit versioned private reads; it never changes those filters or treats a
root UUID as a legacy version. It grants no delegation, collection, send, rendering,
submission, public sharing or worker activation.

## 1. Implemented Store operations and proposed HTTP assembly

The following Store methods are implemented under the updated owner-decision process. verified_user is the
server-verified user ID, never a request body field or ingestion bearer identity.

```text
list_private_artifacts_v2(verified_user, responsibility_id, *, limit=20, before=None)
read_private_artifact_v2(verified_user, artifact_id)
read_private_artifact_evidence_v2(verified_user, artifact_id, *,
    group, index, check_id=None, first_slot=0, limit=1)
```

M may assemble them, after separate implementation review, as:

```text
GET /v2/responsibilities/{responsibility_id}/artifacts
GET /v2/artifacts/{artifact_id}
GET /v2/artifacts/{artifact_id}/evidence/{group}/{index}
```

Store implementation does not register these routes. Use the existing verified Clerk session dependency,
no-store on every response/error, strict allowed query keys and no mutation/retry.
Only the list accepts limit/before; only evidence accepts check_id/first_slot/limit.
No endpoint accepts user IDs, source/root IDs, purpose/TTL, policy, provider URLs,
report bodies or connection configuration. A citation index selects a reference
already saved in that exact artifact/check, not arbitrary course content.

All methods restrict artifacts.evidence_schema=2. Old schema1 artifacts stay on
existing v1 reads; there is no coercion or v1 sidecar promotion in this slice.

## 2. List: bounded metadata, not a new readiness decision

An owned responsibility returns:

```text
{schema_version:2, artifacts:[{id,task_id,created_at,saved_state,memory_stale}],
 limit, next}
```

saved_state is the persisted review/ready/needs_revision enum. memory_stale compares
artifact and current responsibility revisions; false alone says nothing about
freshness or permission. List contains no title, body, quote, report or source data.
It may show retained owned history after a connector is disconnected. UI labels the
state as a saved check state and opens detail before displaying content or evidence.

limit is an exact integer1–50 (bool rejected). Stable ordering is created_at DESC,
id DESC; fetch limit+1 to determine next. before/next is null or the pair
{created_at,id}, exact aware UTC timestamp and canonical UUID. M encodes it as a
base64url JSON cursor of at most512bytes, not a capability. Unknown/extra cursor
fields reject. A reauthorizes responsibility ownership on every page; tie-breaking
and exclusive comparisons must avoid duplicates. Pages are not a cross-request
snapshot; newer rows may appear only after refresh. Empty owned list is200/[];
unknown or other-account responsibility is indistinguishable404.

## 3. Detail: immutable draft plus separately observed current evidence

Successful content detail returns exactly:

```text
{schema_version:2,
 artifact:{id,responsibility_id,task_id,created_at,memory_revision,
           saved_state,memory_stale,draft},
 controls:{agent_paused,responsibility_status},
 latest_check:null|{id,created_at,memory_revision,report},
 evidence_status:{evaluated_at,state,reasons},
 limits}
```

Draft is the existing strict DraftArtifactV2: schema_version2,title,body,disclosure
and citations[{claim,evidence}], at its existing bounds. An unchecked artifact may
be inspected with latest_check=null; its evidence_status is unverified until all
available saved references are assessed. A read never creates a check or infers
policy from absent data.

Report is an explicitly validated projection of the latest saved check (ordered
created_at DESC,id DESC), not arbitrary internal JSON. Fields are passed, errors,
assessment, policy, rubric and limits. assessment is null or existing Assessment;
policy is CoursePolicyV2; rubric is a list of at most30 RubricItemV2. Errors are
bounded stable server codes (at most100, each at most128characters); unknown codes
map to check_unavailable and make the projected check unverified, never echo
exception strings or preserve passed=true with errors. A passed projection requires
a validated boolean passed=true and an empty error list. limits is server-owned UI
text. Raw typed_evidence proofs, model prompts, context bodies, tokens, provider
references and internal diagnostics are omitted. Malformed/oversized legacy-shaped
check JSON must not appear as passed: expose latest_check=null, unverified with
check_unavailable. Do not silently truncate a report or a draft.

Evidence status state is one of current, stale, incomplete, historical, unverified.
Derive it from current reads of the draft's citations and, when present, the latest
check's policy/rubric references. Precedence: unverified for missing/invalid proofs,
then historical, incomplete, stale, current. memory_stale also prevents current.
Return only allowlisted reason codes. Even current plus a saved passed check is
**inspection evidence, not drafting/delivery authority**. Show “checks passed when
saved” and explicit current gaps; never translate the saved ready enum into permission
to send or submit. All actions still use existing independent current authorization.

## 4. Authorization and control timing

A owns one coherent read transaction under the existing agent-before-responsibility/
connection lock order, reused rather than a parallel permission system. Check
verified account ownership, current responsibility bindings, selected course/resource,
connection subject/generation, connected state and credential expiry before loading
or returning content. Direct legacy references must be genuinely bound source versions;
Canvas-mapped inline versions also require current Canvas authority. A stored quote,
artifact ownership or prior passed check alone cannot bypass those checks.

If current source authority is unavailable (disconnect, scope removal, subject/
generation change, credential expiry), return SourceRefreshRequired, no content
or report. Do not return the immutable draft's embedded quotes around this denial.
Wrong account, unknown artifact or wrong schema is generic LookupError/404 instead.
An authorized but old/partial/historical source can be inspected with honest status,
never silently replaced with latest. An unchanged sync can make old observations
historical even when text/root is unchanged; retain exact pinned identity.

Pausing the agent/responsibility prevents work, not the student's authorized read of
saved content. Return agent_paused and the real active/blocked/done responsibility_status; there
is no persisted per-responsibility pause flag to fabricate. No task lease is needed or
manufactured for student inspection. Reads never resume work, refresh credentials,
re-pin evidence, advance timestamps or revise artifact state. Recheck credential
expiry and current control/connection authority before finishing the bounded read;
return evaluated_at from the server clock. A later change after return cannot recall
already displayed bytes. UI refreshes detail on reopening; it cannot use cached
availability as an action grant.

Server-owned inspection freshness remains Canvas24h and direct legacy24h; generation
retains Canvas6h/direct legacy24h and existing urgent/action policies. Do not run the
draft-only _typed_drafting_context helper as a student read: its current/complete6h
contract is intentionally stricter. Reuse original read/proof/freshness primitives
with purpose=inspect and separately labeled metadata. The student cannot choose TTL.

## 5. Evidence read: exact original behind a saved reference

Allowed group/index pairs are citation/0–29, policy/0, rubric/0–29, with exact integer
bounds and actual list membership. Policy/rubric require the exact check_id returned in detail, checked against the
same owned artifact. Read that immutable check, never whichever check became latest
after the student opened detail. Citation requires check_id=null and reads the
immutable draft. Return the selected check_id in the response. A check ID is not
a capability: repeat current source authority checks and reject a check from another
artifact/account. Missing group/index/check is generic404; missing required check_id
or an unexpected check_id for citation is400. A newer check may be shown after an
explicit detail refresh; no index or source is silently re-pinned.

Every reference retains its discriminant and exact existing fields:

- legacy: kind,version_id,quote (up to2000codepoints).
- canvas_document: kind,object_id,observation_id,document_version_id,segment_id,
  slot,page,start,end,quote (up to4000codepoints). Document offsets are global Unicode
  codepoints in normalized original text, not UTF-16/browser string indices.

Response:

```text
{schema_version:2,artifact_id,group,index,check_id:null|UUID,reference,
 quote_matches,source,evidence_status}
```

A document source has kind=canvas_document, the pinned object/observation/root IDs,
sections[{segment_id,slot,page,start,end,text,text_sha256}], next_slot,total_slots,
coverage,missing,historical,freshness. first_slot is an exact integer0–512; limit1–20;
reuse existing at-most40000codepoint page bound with explicit next_slot. Validate the
saved citation's original slot/hash/quote even when the requested page is another
page of that same pinned root. Verify all object/observation/root/segment links; no
arbitrary-root fallback or uncited-object browsing. Blank/unrepresented PDF pages
remain gaps, not invented text.

A legacy source has kind=legacy,version_id,title,content,historical,freshness;
first_slot must be0 and limit1 (default). Existing complete legacy content bound is
retained; no implicit conversion to sections and no unsafe external source URL.
Exact quote inclusion must be checked against the owned original. Both branches
report evidence_status as above; quote_matches alone is not current usability.

All successful detail/evidence responses are at most1MiB serialized UTF-8, using
existing source/document bounds. Exceeding budget fails explicitly, never clips
citations, original text or restrictions. No content is logged; UI renders text,
not executable source HTML. No signed downloads, remote fetches or public files.

## 6. Errors, delivery order and acceptance

A errors: invalid strict input→ValueError; owned source authorization lost→
SourceRefreshRequired; wrong/missing account/artifact/check reference→LookupError;
response budget exceeded→PrivateArtifactReadLimit from
shared/private_artifact_projection.py. M maps to redacted400,
409{code:source_refresh_required}, indistinguishable404 and413{code:read_limit}.
Authentication failure is401; database unavailable503, unexpected redacted500.
No exception/source text in response/log. Every response, including401/404/413, is
no-store. No refresh/send/model/other external IO is implicit in any read.

Delivery sequence: A has implemented versioned Store projections/tests. M reviews concrete code
and implements owned session routes/UI
against it; incompatibilities are raised asynchronously, without a mandatory design
agreement pause. A reviews/integrates the combined consumer.
Existing v1 filters stay until an explicit later migration decision. No new SQL is
assumed necessary; justify any discovered schema need separately.

Required A tests: mixed original references with no fake legacy rows; other-account
and schema denial; old/new observation identity; scope/subject/generation/expiry and
final-clock revocation; pause with no side effects; current versus saved check state;
malformed/missing check; exact Unicode/hash/page proofs; wrong group/index/check/root and a new check arriving between detail and evidence;
keyset ties/limits/mutations; oversized response without truncation; no v1 change.
M tests session-only access, error/no-store/query/cursor boundaries, truthful UI
labels and exact source display, with no body injection or internal JSON leakage.
Run combined HTTP/Store/UI tests before exposing results. Scripted evidence is not
live Meta quality, installed Canvas or WhatsApp/continuous-agent acceptance.

Requested review: flag concrete method/DTO/paging/authority incompatibilities while
A proceeds with owned implementation. There is no mandatory acknowledgment gate.
The Store code and acceptance evidence are linked above. HTTP/UI activation and
M's independent collection work remain separate.
