# P1 document root validation — November 1, 2026

Owner Akbar/Codex; [claim6554801320](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6554801320).
Branch `codex/p1-document-root-validation`, base #128 `1cbb61d`.
Executable revision `5d46e73fa70fcab6cd90e987b65a0f3a2afa1ca5`.

## Behavior

The exact #118 document design is agreed at7f4f09f by M in
[6554751370](https://github.com/Akbarhoja/wrytely-agent/pull/118#issuecomment-6554751370).
`shared/canvas_document_wire.py` implements its pure finished-root validation.
It reuses the existing section validator, schema1 EvidenceItem field canonicalization
and canonical_source_bytes algorithm. It does not add a second parser or store.

Exact resource/owner/metadata keys, supported resource-kind pairs, numeric file IDs,
configured extractor IDs, bounds, timestamps, file fields and coverage are checked.
Section text must match the manifest hashes, offsets, Unicode normalization and
page provenance. The agreed limits remain200000 code points/512 slots/24000 per slot/
200 PDF pages. Missing pages or empty text need explicit missing evidence; they
cannot be certified complete. Long text is represented by its verified manifest,
not clipped to a short-body prefix.

Root identity includes owner kind and canonical assignment/syllabus/page or file
fields. Changing a deadline or rubric changes the root even if text is unchanged.
Course/provider identity and provider_updated_at remain separate validated provenance.
Frozen output stores immutable sections, canonical UTF-8 and SHA256; its payload
property returns a detached dictionary. Caller-owned inputs cannot mutate the result.

## Verification

-98 new pure tests pass, including all10 unchanged agreed vectors with exact canonical
  bytes/SHA256, Unicode expansion/surrogates, field tampering, bad keys/types/bounds,
  invalid provenance, gaps/empty coverage, configured extractor IDs, file metadata,
  schema1 assignment validation, deadline/rubric changes and full200000-character text.
- Existing sections plus new roots:151 focused tests pass.
- Full combined disposable-Postgres backend:1062 passed, zero skips, two existing
  warnings in51.37s. Existing schema1/API/storage behavior remains covered.
- Ruff check/format176 files and diff checks pass. No existing digest or document
  fixture, schema1 contract, app/extension/integration/runtime/SQL file changed.
- Previous #128 integration CI41283546158 completed SUCCESS on its exact1cbb61d,
  separate from this increment's local evidence.

## Boundary and next work

This is validation of an already assembled document, not a staging request/receipt
parser or proof of scan ownership. Trusted extractor configuration is a caller input;
no source text can select executable code. No provider IO or extraction occurs.
The next A slice must add staged transactions under current verified scan/lease/
scope/expiry/quota fences and invoke validation at finish. Publication must remain
atomic and private. M retains extractor/HTTP/extension implementation and review.

Counterpart review is required; internal storage #124 and integrated candidate #128
remain separately reviewable. M's active #127 two-course harness is not modified or
claimed passed by this helper. Exact #119 design agreement also does not activate
new action/dispatch consumers.

No live source/model request, credential grant, WhatsApp send, retained migration,
installed extension change, continuous worker, deployment or protected-main merge.
P0/P1 remain open; Outlook is optional/paused and WhatsApp delivery remains M-owned.
