# Private v2 draft and original evidence reads

A-owned complete Store feature on codex/private-artifact-results, based on
#163 `027da3f`. [Feature coordination6569889208](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6569889208).
The supervisor removed routine design-agreement gates; implementation proceeded
inside A's Store/runtime/contract ownership. M retains HTTP/UI and collection wiring.

## Implemented behavior

The existing Store now composes PrivateArtifactReadStore. New methods are:

```text
list_private_artifacts_v2(verified_user, responsibility_id, *, limit=20, before=None)
read_private_artifact_v2(verified_user, artifact_id)
read_private_artifact_evidence_v2(verified_user, artifact_id, *,
    group, index, check_id=None, first_slot=0, limit=1)
```

[The versioned boundary](contracts/PRIVATE-ARTIFACT-READ-v2.md) records fields, bounds,
errors and HTTP assembly requirements. No old v1 artifact/result/status method
changes, and no internal document root is disguised as a legacy version_id.

List returns at most50 content-free metadata rows ordered created_at/id descending,
with an exclusive keyset cursor. Acknowledged cursor dates are emitted in UTC even
when the PostgreSQL session uses a local timezone. Empty owned lists and unavailable
responsibilities stay distinct internally; wrong accounts get generic Not found.
Retained metadata does not require reconnecting and never implies current readiness.

Detail validates DraftArtifactV2 and projects only bounded, typed saved-check fields.
Unknown error codes, malformed assessment/policy/rubric, inconsistent passed flags,
wrong evidence schema or coverage counts hide the check and mark it unverified.
Raw internal proofs, usage, credentials and provider URLs are not projected. Pausing
work does not prevent authorized student inspection. Controls expose agent_paused
and actual active/blocked/done responsibility_status; there is no duty pause flag
in the current schema.

Source inspection uses current account/responsibility bindings, connection subject/
generation, selected resource and credential authority under one agent-first
transaction. Every explicit object binding is checked, including uncited objects.
No lease or active-work status is manufactured. Permission loss rejects the entire
content read, including embedded draft quotes/report. Direct legacy sources need
the actual responsibility binding; Canvas-mapped inline sources also use current
Canvas authorization. Historical source IDs/observations never fall back to latest.

Evidence reads select only saved citation/policy/rubric entries. Policy/rubric require
an exact immutable check_id belonging to the same artifact, so a newer check cannot
silently change the selected reference. Mixed legacy/document evidence retains its
actual kind. Documents reuse existing bound-root/section/hash/quote validation and
40000codepoint paging, with original segment, page and global Unicode offsets.
A requested page can differ from the cited slot; quote validation still checks its
original slot. Legacy originals remain whole bounded source versions, not fake sections.

Saved check state is separate from current inspection state: current, stale,
incomplete, historical or unverified. Canvas inspection uses24h, never substitutes
for drafting6h. Old observations after an unchanged refresh remain historical; memory
revision changes are visible. Current scope/connection/credential clocks and metadata
are checked again before completion. Responses over1MiB fail intact with the dedicated
PrivateArtifactReadLimit; originals/restrictions are never silently clipped.

## Verification

- New feature suite:46passed, zero skips,8.28s. Includes actual published document-only
  and mixed originals, direct legacy/v1 compatibility, metadata-only tied-date keyset
  paging, strict inputs, paused inspection, source scope/revoke/expiry/subject/generation/
  binding denial, wrong account, malformed/missing checks, pinned old check selection,
  exact quote mismatch, original paging and complete large-response rejection.
- Final source expiry injected after loading prevents returning already-loaded
  content; aging an original during reading downgrades the returned final metadata.
- Initial cursor round-trip test reproduced a defect in emitted PostgreSQL local-time
  cursor dates; normalizing the emitted anchor to UTC fixed it. A later missing test
  helper import was corrected; no production protection was relaxed.
- Full combined fresh disposable backend:1,531passed, zero skips, two existing
  warnings,116.63s. All460extension Node tests pass; Ruff lint/format238files pass. Scoped docs/links/diff/path checks apply.
  Counterpart feature review and new CI remain separate.

## Handoff and remaining scope

M can now implement the documented verified-session list/detail/evidence HTTP routes
and website UI as one connected consumer, without another mandatory design pause.
Use only returned whitelisted fields; render source/draft text safely. Map read-limit,
refresh, not-found and invalid-input errors without exposing exception text; set
no-store on success and every error. Cursor encoding belongs to HTTP assembly.
“Checks passed when saved” and current inspection status must remain separate; no
read result authorizes drafting, file delivery or submission.

No app route or website consumer is registered by this feature. No source/parser/
journal, model tool, generator, schema migration, worker activation, live provider
call or delivery was added. The publication HTTP/journal gap remains M's separate
collection dependency. Existing oversized drafting-context limits remain intact.
P0 baseline human approval/merge and WhatsApp delivery remain open; P0/P1 are not
complete. No live source/model/send/spend/grant/install/retained migration/deploy/
main merge occurred.
