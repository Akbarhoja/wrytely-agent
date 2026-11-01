# Canvas academic HTTP implementation plan

> **For agentic workers:** Use superpowers:executing-plans with TDD and one fresh whole-branch review.

**Goal:** Expose existing bounded C2v1 academic transactions through private HTTP assembly.

**Architecture:** Add strict academic batch/resource DTOs and two routes to the existing Canvas registrar. Reuse Control/Checkpoint, AcademicBatch, CanvasRoute body caps and Store commit/finish methods; do not create a parallel persistence/authorization path. Existing discovery requests retain their current behavior.

**Spec:** [#111](https://github.com/Akbarhoja/wrytely-agent/issues/111), [P1-M1](../../WORK-ORDERS.md), implemented C2 academic contract in CONTRACTS.md. Base `c82b996`; M-owned branch `codex/canvas-academic-http`.

## Constraints

- Four claimed app/API-test/scoped-doc files only; no shared/runtime/schema/CI/STATUS edits.
- Authenticated ingestion credential, exact schemas,2MiB streamed wrapper and existing1MiB Store envelope;64KiB resource controls.
- Title<=300/content<=24000 after NFC/newline normalization. M's HTTP bound check does not mutate text, replace canonical hashing or fix shared persistence; A#98 remains required in consolidation.
- Only current AcademicBatch resource kinds. No schema2/documents/modules/files completion, raw HTML conversion or clipping.
- Store remains authoritative for ownership/subject/generation/scope/lease/checkpoint/replay/resource ordering and atomic staging.
- No model/source promotion, live provider/account read, grant/send/spend/install/host/deployment/main merge. Outlook optional/paused; P0 access A-owned under newer #4/#105 record.

## Task 1 — private academic assembly

- [x] Add actual Store/API tests for staging/receipt replay/finish, all supported kinds, incomplete-resource denial, authority/races, malformed/normalized/size inputs and sanitized failures. Run RED before routes exist.
- [x] Implement strict DTOs and routes using existing dependencies/dispatch/body caps; preserve discovery handlers and controlled errors.
- [x] Run focused new plus existing Canvas API suites, required Ruff/format/full disposable backend,233 Node/web/TypeScript and formatting/diff checks.
- [ ] Fresh review, verified regression fix pass for any blocker, then commit/push draft PR with exact evidence/limits and request A review/serialized STATUS.

## Review focus

- Session credentials cannot masquerade as ingestion credentials; metadata/body never determines ownership.
- Partial/blank-title normalized expansion cannot evade public HTTP bounds on this historical C2 base.
- Academic completion must use Store manifests and cannot close an incomplete/unselected resource.
- Changed-body retries cannot reuse receipts; source versions remain staged and check times do not advance on replay.
- Existing discovery API and unknown/error no-store behavior stay compatible; schema2/document gates remain explicit.
