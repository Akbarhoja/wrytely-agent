# Document HTTP dependency review

Murtazo claim [#147](https://github.com/Akbarhoja/wrytely-agent/issues/147).
This branch contains two new documents only. No runtime, shared, contracts, app,
extension, configuration, CI or STATUS changes. HTTP implementation waits for the
explicit decision requested in [the proposal](P1-CANVAS-DOCUMENT-HTTP-PROPOSAL.md).

## Exact dependency inspected

A #135 `019d6c7e6e62e4023dab72cb1fb3d4415a764c9e`, based on #134 `81f000a`.
Read the complete finish transaction, additive017 ownership constraints, protocol
fingerprint extension, original receipt handling and new regression tests.

The implementation reassembles existing immutable parts, validates the agreed
whole root (including NFC across section boundaries), and reuses015 private
sections. A root fingerprint adds protocol digest only for protocol callers;
legacy section fingerprints stay unchanged. Deadline/rubric/metadata changes can
therefore distinguish roots even when section text is identical. Ready pointers
are ownership-bound and final receipt authorization/expiry checks remain in the
same transaction. No observation or source readiness is manufactured by finish.

Independent exact-head focused verification completed on a new disposable Windows
Postgres database: **86 passed in326.42s**, no skips. Command: native Python pytest
tests/test_canvas_document_uploads.py tests/test_canvas_documents.py. This covers
57 upload/finish and29 document-storage cases, including missing/expired parts,
whole-text normalization, field-aware root identity/reversion, parallel finish,
final-lease rollback, scope/revocation/generation/account/extractor denial and
unchanged legacy section behavior. No scoped blocker found in the read review.
No author-owned file is edited; this is not a full#135 inherited-stack rerun.

## Proposal consistency review

A fresh read-only reviewer confirmed the Store signatures, current authorization
before receipt recovery, immutable receipts, trusted extractor input and separate
publication boundary. It caught an important draft mismatch in proposed errors:
schema1 transport conventions had been copied instead of document-wire section5.
Corrected the proposal to preserve400 validation, empty-body404 and bounded429
retry hint. The proposed30-second header remains explicitly for A agreement; it
does not guarantee when quota capacity returns. No protocol amendment or actual
HTTP implementation is claimed. No critical findings or deferred minors.

Review limits: no HTTP code or executable route-acceptance tests yet. The author
verified dependency tests and current GitHub state separately. Installed-browser
access, publication, extractor completeness, provider delivery, deployment and full
P1 readiness remain separate and cannot be inferred from this focused review.

## Limits and current project state

No installed Chrome, source, provider, model, send, grant, spending, production
migration, deployment or protected-main action. Chrome remains untouched; Codex
automation stays off. #144 CI41330046750 and #146 CI41333618400 passed, but A
counterpart review/integration and real-browser development configuration/P0 scope
remain pending. P0 WhatsApp delivery is open; Outlook is optional and paused.

Unchanged application code does not need a redundant full executable suite for
this documentation-only branch; formatting, relative links and diff checks apply.
Focused dependency tests are separate from prior full component/CI evidence.
