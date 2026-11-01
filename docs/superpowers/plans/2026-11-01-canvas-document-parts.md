# Canvas document parts implementation plan

> Use superpowers:executing-plans inline, with one fresh final code reviewer.

**Goal:** Produce bounded original-text section manifests for the agreed v2 wire.
**Architecture:** One pure browser module; existing digest helper and Python
validators prove compatibility, without duplicating storage/root validation.
**Tech Stack:** Native JavaScript/Web Crypto, Node test runner, pytest/Postgres.
**Spec:** [stage](../../stages/P1-CANVAS-DOCUMENT-PARTS.md).

## Global constraints

Own only the five #149 files. Default24000 chars/slot;512slots/200000 normalized
code points/200PDFpages/1MiB rawUTF8/400000 rawcodepoints. Never clip or infer
coverage. No source IO, storage, publication, host/UI/CI/shared changes.

## Review focus

- Astral/combining/CRLF boundaries preserve exact text and code-point offsets.
- Empty PDF pages preserve gaps without synthetic text or coverage claims.
- Raw/normalized limits reject the whole operation before async hashing.
- Input changes while hashes await cannot mix versions of manifest and parts.
- Invalid getters/containers/Unicode cannot leak source text in errors.

## Task 1: Pure producer and cross-language acceptance

Files: new extension/canvas/document-parts.mjs, its .test.mjs,
tests/test_canvas_document_parts.py and the two scoped stage/plan documents.
Consumes unchanged approved v2 vectors, source-digest.mjs and existing Python
validate_canvas_document/validate_document_sections. Produces the stage's exact
prepareDocumentParts signature and manifest/parts/totals/gaps.

- [x] Write fixture parity, normalization/page/limit/privacy/mutation Node tests
      plus Python acceptance over actual JS output. Run focused Node; Expected RED
      missing document-parts.mjs before implementation.
- [x] Implement bounded snapshot/normalization/code-point splitting/SHA256.
      Run focused Node and cross-language pytest; Expected all PASS.
- [x] Run full Node, uv Ruff lint/format and full disposable pytest; Expected
      zero failures/skips. Fresh final read-only review, fix Important findings with
      RED→GREEN, record evidence, commit and publish draft PR/A handoff.

## Ledger

Claim#149 resumed in #4 before edits; base019d6c7. #155 API is separate and green,
not copied into this branch. No task shares mutable implementation files with A.

Draft integration target initially A#153, then updated to current complete
A#158385d5b2 after handoff6565287783, preserving approved branch base019d6c7.
Merge-base is019d6c7; only five owned additions enter review. Existing target
CI globs include producer tests without M editing A-owned CI. Both ignored exact
overlays passed460Node/14cross-language tests. Final local1150backendPASS,
421NodePASS,14cross-languagePASS; proxy privacy finding fixed with8RED→GREEN
regressions. No other reviewer findings/minors. Remote combined CI and counterpart
review remain separate; exact published head is recorded in the claimed issue/PR.
