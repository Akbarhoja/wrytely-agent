# P1 document-parts producer integration

A/Codex review/integration under
[claim6567577999](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6567577999).
M delivered [#159](https://github.com/Akbarhoja/wrytely-agent/pull/159), exact
`95465a82c99e481cebd42a64f1f245152ee2b37b`. It targets the complete #158
`385d5b25ba984a28efc7c17b467af8d426c29370` candidate while retaining its approved
#135 implementation base. The merge adds only five M-owned files; each is
byte-identical to the delivered head. A additionally serializes STATUS, this review
and the received P0 Canvas classification decision. No implementation fix was made.

## Review

No blocking finding in the scoped read review. prepareDocumentParts takes already
extracted text or ordered PDF page strings, never fetches or parses files. It
validates/snapshots input before asynchronous hashing, normalizes LF/NFC before
Unicode code-point splitting and hashes exact normalized UTF-8 section bytes.
PDF pages keep original numbers; separators belong to the following nonempty page,
while blank pages retain explicit unrepresented_pages without invented sections.

Raw input, UTF-8 bytes, normalized characters, pages, slots and per-section sizes
are bounded; invalid input rejects the entire result without clipping. Property
inspection rejects accessors and redacts throwing/revoked proxy exceptions. Terms
such as ready, permission or coverage are not output or inferred. The returned
manifest/parts/totals remain compatible with the unchanged agreed vectors and
Python validators. No producer input becomes server authority.

The current CI directory globs automatically include the56new producer Node cases;
no CI change is needed. The helper remains unbundled/unwired. It does not add
transport, upload journal, publication, extraction or collection activation.

## Independent combined validation

- All460extension Node tests pass, zero skips;56new producer cases included.
- All14actual JavaScript/Python cross-language cases pass, zero skips,0.18s.
  Approved10canonical vectors retain original manifests/hashes; long astral text,
  normalization, PDF page gaps and section limits pass unchanged Python validators.
- Full combined fresh disposable backend:1,463passed, zero skips, two existing
  warnings,103.26s. No retained database selected.
- Ruff lint/format230files, scoped producer/document Prettier, delivered byte audit
  and diff checks pass. New evidence links/format are checked before publication.
  Candidate CI is separate from local results and M's earlier base checks.

## P0 decision and next ownership

M's [Canvas classification acceptance6565232797](https://github.com/Akbarhoja/wrytely-agent/pull/139#issuecomment-6565232797)
was received and serialized into the [closure record](P0-CLOSURE-2026-11-01.md).
Signed-in/tab/session-required feasibility is technically accepted with every
recorded live gap retained. Unattended/MV3 reliability, positive rubric access,
second-account switch, natural expiry and complete pagination are not proved.
Fresh #46 inspection still shows open/unmerged/blocked and zero formal reviews.
Independent human approval/protected baseline merge and WhatsApp delivery remain
open; Outlook stays optional/paused. P0/P1 are not marked complete.

M retains producer-to-existing-journal/upload/publication assembly and private
HTTP/UI ownership. #157 private-result interface still awaits explicit agreement;
no dependent consumer implementation was started. This integration is technical
review, not independent human GitHub approval or installed/live source proof.
No source/model/send/spend/grant/install/restart/retained migration, continuous
worker, deployment or main merge occurred.
