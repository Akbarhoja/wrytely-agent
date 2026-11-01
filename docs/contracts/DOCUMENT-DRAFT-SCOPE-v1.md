# Document-only drafting and task scope — v1 proposal

Owner A designs runtime/store/contracts; M reviews consumers and owns HTTP,
extension and UI assembly. **Proposal only: counterpart agreement is required
before dependent implementation.** This does not activate a source, grant an agent
semester-wide access, authorize drafting, add a route or deploy a worker.

The current internal guard in [#141](https://github.com/Akbarhoja/wrytely-agent/pull/141)
can check pinned document provenance for a legacy-backed draft. It deliberately
cannot draft from a document-only publication whose source_id/version_id is null.
Creating fake text versions or weakening the existing task reader would hide that gap.

## 1. Reuse the existing workflow

Retain the responsibility, memory-revision, task lease, student decision,
policy-preflight, generation, verification and bounded revision machinery. Extend
its evidence references and explicit source bindings. Do not create a parallel
agent, accept browser-selected user IDs or make manual uploads the normal flow.

The collection-to-work sequence should be:

1. M's collector publishes complete or explicitly partial Canvas documents through
   the existing protocol. Collection alone grants no drafting permission.
2. A's future supervisor discovers an evidenced assignment through a separately
   reviewed semester-read capability, then offers work over M's messaging assembly.
3. A current explicit student delegation supplies the exact assignment objects to
   the shared authorization boundary. M's assembly derives identity from its
   verified session or matched student decision, never from a submitted user ID.
4. A atomically creates the responsibility and bounded document-object bindings,
   persisting a replay specification and task under the owning agent lock.
5. A's task reader loads pinned original sections in bounded pages. Requirement
   extraction, policy checking and generation use document evidence references.
6. A saves/verifies the draft and rechecks all referenced evidence at final commit.
   Delivery remains a distinct reviewed authorization, not a side effect of drafting.

Steps2–6 are not implemented by this proposal.

## 2. Explicit object scope, not synthetic legacy sources

Proposed additive table responsibility_canvas_objects stores:

`agent_id, responsibility_id, object_id, connection_id, connection_generation`.

Use composite ownership FKs/unique keys; the object must belong to that same agent
and connection. The server derives connection ID/generation from the owned object.
A trusted task read may use a current legacy responsibility_sources binding **or**
this explicit object binding; account ownership alone remains insufficient.

A binding is invalid after scope removal, subject/generation change, disconnect or
credential expiry. Task pause/lease/revision fences remain mandatory. Do not let a
model, ingestion bearer or collection request create these bindings. Scope mutation
must advance responsibility revision and fence old tasks. Initial explicit delegation
and bindings must commit atomically; a failed bind leaves no half-created task.

Object scope allows investigating the object's current observation; each actual
read/citation still pins an exact observation, document root and segment. An explicit
reference miss never falls back to latest. Changed roots/observations cannot silently
replace evidence in an already saved draft. Unchanged-sync freshness semantics must
be tested explicitly against the existing observation/history rules before claiming
that cached drafts remain usable across refreshes.

Proposed internal signature:

```text
create_canvas_draft_responsibility(verified_user, objective, request_key, *,
    object_ids, max_steps=6, max_revisions=2, pending_limit=20)
```

Use1–8 unique UUID object IDs, objective1–12000 characters after trimming,
request_key1–128 characters, max_steps1–12, max_revisions0–2 and pending_limit1–1000;
integer limits reject bool. Canonicalize object IDs and persist the sorted scope,
objective and limits for exact replay. Require current selected published objects
with connected, unexpired credentials; the connection subject/generation must match
the stored object/observation. Full completeness remains a separate drafting gate.

Wrong account/object identity returns generic LookupError("Not found"); unavailable
current connection/scope returns SourceRefreshRequired; invalid bounds/duplicates
raise ValueError; changed request-key specifications raise RequestConflict; pending
capacity raises QueueFull. Reuse existing typed error mapping only after M agrees
its HTTP projection. Initial bindings, intent, replay specification and task commit
atomically, so errors leave no half-created responsibility. These are proposed
semantics, not an implemented method or route.

## 3. Versioned typed evidence references

Propose a new explicit v2 evidence reference, preserving old external DTOs until
M agrees migration/consumer handling:

- `kind: legacy` carries the existing version_id and exact quote.
- `kind: canvas_document` carries object_id, observation_id, document_version_id,
  segment_id, slot, page, start, end and exact quote.

Draft claims, course-policy evidence and rubric evidence must all use the same
reference family. Document roots must not be stuffed into legacy version_id.
Mixed legacy/document evidence must be supported explicitly, not silently dropped
or coerced into a fake common source. The current internal all-citations provenance
array in #141 is a compatibility guard, not this v2 contract.

Retain current exact quote/Unicode/hash/offset/page limits and bounds on claims,
rubric and payload size. Source fields can propose policy interpretation; they
cannot override student permissions or the final deterministic checks. Unknown,
conflicting, missing or incomplete policy/rubric evidence prevents a ready draft.
A model summary can point to a section but is never its original-source substitute.

## 4. Generation and verification order

Load context through the fenced task scope, page full original sections and expose
explicit continuation/completeness. Do not truncate a long document to a legacy
24,000-character source or send an entire semester into one prompt. Establish
bounded retrieval/model budgets and record when additional investigation is needed.

Apply server-owned draft freshness to every policy, rubric and factual reference
before generation/preflight and again before final readiness. Require complete current
coverage for permission/completeness claims. Missing content is not evidence of an
absent restriction. An unavailable source stops the workflow for refresh/reconnect;
prose revisions cannot repair a revoked credential or stale observation.

Keep immutable draft provenance and replay specifications. Recovered work rechecks
current bindings, selected scope, subject/generation, exact original sections,
coverage, freshness, memory revision and lease. Do not trust a previously passed
report as authorization. A policy recheck cannot manufacture student delegation.

## 5. Ownership and acceptance before enabling

A implements additive store/schema changes, scoped reads, typed references,
requirement/generation/verification changes and their tests. M agrees the boundary
and implements any new authenticated route, decision-to-delegation assembly and
versioned private-result UI. M's Canvas host/collector remains his existing claim;
no ownership is transferred by this proposal.

Required tests include complete document-only positive workflow with no fabricated
source_versions; long/paged and mixed evidence; exact policy/rubric/claim provenance;
wrong account/task/object/root; scope/subject/generation changes; partial extraction;
refresh with unchanged text; changed requirements during generation; exact/conflicting
replay; pause/expired lease; interruption/recovery; no extra revision inference after
evidence failure; no automatic send/submission. Run the combined consumer/runtime
suite before enabling any actual assembly. Live Meta quality and Canvas/WhatsApp
operation need separate bounded evidence and existing approvals.

Requested M review: agree or amend object-scoped delegation, v2 evidence shape,
consumer versioning, the proposed1–8 object bound, error/replay behavior and the
order of the first implementation slice. No code may assume agreement from silence.
