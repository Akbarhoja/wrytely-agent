# P1 atomic document publication — November 1, 2026

Owner A; [claim6555410948](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6555410948).
Branch codex/p1-document-publication, base #135019d6c7; executable7339a59.

## Implemented behavior

The existing commit_sync_batch entry dispatches only the agreed exact schema2/
canvas_documents envelope into a new strict model. Staging operation fields and
mixed inline content reject; schema1 models stay unchanged. The same replay-key
namespace preserves conflicts across schema versions. Ready root identity, current
owned scan/connection/generation/subject/scope/resource/lease/expiry and checkpoint
are checked. Metadata must match the staged header and parts/root integrity is
reverified through the existing015 loader. A root digest is never lookup authority.

One transaction creates observations, pins their root bindings, records resource
items and structured events, advances the checkpoint/check count, marks uploads
published and saves the exact receipt. A malformed/missing second upload or final
lease failure rolls all of it back. No legacy source_versions entry with an empty
body is created and no existing latest source pointer is promoted.

Unchanged observations reuse roots without duplicate change events. Changed dates/
rubrics remain original field-name changes. A→B→A retains transition observations
while reusing immutable roots. Historical captures cannot replace latest pointers;
conflicting same-instant content rejects. Existing source-bound work is invalidated
on actual source change rather than allowed to use stale evidence.

Additive018 marks inline/documents resource mode and published uploads. Mixed modes
within a resource scan reject in both directions, even across pages. Complete
resource finalization includes document digests and file scope, while incomplete/
historical/latest failed scans remain unusable. Published uploads leave the active
unpublished-count quota; retained upload parts remain byte-counted pending safe
cleanup, so this increment does not delete data to release quota.

Metadata reads expose a pinned document root. Protocol documents reject the old
short-body reader instead of returning an apparently complete empty or clipped body.
The existing bounded original-section reader validates exact object/observation/root
identity and all current privacy/freshness/lease fences.

## Verification

All27 new synthetic disposable-Postgres cases pass. Full combined backend1163PASS,
zero skips, two existing warnings68.49s at7339a59. Ruff lint/format188files and diff
checks pass. Existing19 actual HTTP cases remain in that full suite unchanged.

Tests verify:

- Atomic ready-root publication and original receipt replay, with no fake legacy
  text version; pinned section reads and cross-account/root denial.
- Repeated/changed-deadline/reverted content: root reuse, new observations and exact
  original-field event/previous-observation links without duplicate events.
- Unknown/unready/wrong-owner/wrong-title uploads, outside-course references,
  duplicate/malformed schema/key/count fields and missing second-item rollback.
- Final lease failure, expired upload/lease, revocation/scope change and cross-account
  publication denial; shared schema1/schema2 replay namespace.
- Inline/documents mode rejection in both directions, incomplete latest scans and
  zero-text restrictions never certifying completion; selected file finalization.
- Full100000-emoji retrieval through <=40000-character whole-section pages with
  explicit continuation; no prefix presented as the full source.
- Historical and same-instant changed document handling with current pointers and
  events preserved. Tests use synthetic data, not private Canvas content.

Initial focused failures exposed fixture replay keys colliding with the deliberate
course-batch namespace and a wrapper supplying changed current generation; tests now
use unique document keys and pass original captured authority directly. Production
replay/context checks were retained rather than relaxed.

## Remaining work

This is shared backend transaction/reader support, not a wired schema2 HTTP or
extension collector. M owns consumers, actual extraction/provider IO, installed host
and browser/session recovery. Independent review of #133/#135 and this implementation
is required; the earlier #132 synthetic two-course proof remains separate.
Safe bounded orphan cleanup remains the next backend slice, preserving all historic
bindings and receipt tombstones. Model-source activation/supervision and live flows
remain later reviewed milestones. P0/P1 are not declared complete.

Only disposable tests received018 (and017 from finish). No retained migration,
live source/model/send/spend/grant/install/worker/deployment/main merge occurred.
