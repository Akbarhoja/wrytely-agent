# P1 ready document finish — November 1, 2026

Owner A; [claim6555344447](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6555344447).
Branch codex/p1-document-finish, base #13481f000a; executable340b599.

finish_document_upload implements the exact agreed #118 finish shape and receipt.
It reuses existing current owned credential/scan/scope/generation/subject/lease and
fixed upload-expiry checks before reassembly and final commit. All immutable parts
are validated with the existing whole-document helper. Incomplete uploads and
whole-text normalization changes across individually valid sections reject.

Private015 section storage is reused with additive017 nullable protocol payload.
Legacy internal fingerprints remain unchanged; protocol fingerprints include root
digest, binding changed academic fields even when body text is unchanged. Owned
A→B→A roots deduplicate. Integrity reads recompute payload/manifest/section identity.
Composite foreign keys bind ready upload pointers to the same agent/object/root.
A shell object identifies the root but has no observation/source pointer; it is
absent from student evidence lists. Finish returns ready:true and immutable root
ID/digest, not published course evidence. It creates no observations, bindings,
checkpoints/events or fabricated legacy short-text versions.

Thirteen new cases verify reassembly, original receipts, missing/expired uploads,
field-aware identity/reversion, concurrent finish, final-lease rollback, strict
wire/current scope/generation/revocation, configured extractors and cross-account
denial. Complete-root checks reject cross-section NFC changes; empty unsupported
PDF evidence preserves missing reasons and no fabricated sections. All86 focused
upload+storage tests pass. Full combined disposable backend1136PASS/zero skips/
2existingwarnings63.36s at340b599; Ruff lint/format184files and diff checks pass.

This follows independent #132 review/#134 combined1123PASS and all19 actual HTTP
scenarios, but no new HTTP consumer is implemented here. Counterpart review and
schema2 publication/cleanup remain separate. Only disposable tests received017;
no live source/model/send/spend/grant/install/retained migration/worker/deploy/mainmerge.
