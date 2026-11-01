# Canvas document upload API implementation plan

> Use superpowers:executing-plans inline; one fresh final requesting-code-review reviewer.

**Goal:** Expose the agreed private staging operations without new storage or activation.
**Architecture:** Reuse CanvasRoute boundaries and existing Store methods; add one
default-off app factory input and a dedicated router with document error mapping.
**Tech:** FastAPI, existing strict JSON/Store validation, pytest/disposable Postgres.
**Spec:** [stage](../../stages/P1-CANVAS-DOCUMENT-UPLOAD-API.md) and linked A agreement.

## Scope and review focus

Claim154: new app/canvas_document_api.py, tests/test_canvas_document_upload_api.py,
minimal app/main.py registration/factory, this plan and scoped stage evidence only.
Current authority on replay, no private error/body leaks, exact document400/empty404,
quota hint not retry promise, default-off trusted config, raw limits before decode,
and unknown committed outcome after failed response are the review focus.

## Task 1: Router and factory

- [x] Write real-Store API tests for all three operations, recreation replay,
      default-off, credentials/control and HTTP boundary behavior. Run focused pytest;
      expected RED for missing canvas_document_extractors factory argument.
- [x] Implement dedicated router and minimal factory registration. Run focused
      tests; expected GREEN with no shared/store edits or new fixture copies.

## Task 2: Verification and handoff

- [x] Complete quota, lost-response/final-lease and redaction tests. Run focused
      tests plus required Ruff/format/full disposable backend and relevant Node.
- [x] Read-only review A#153 CI/integration in an exact archive when independent.
- [x] Fresh final review, fix important findings with observed regressions, record
      evidence/limits and publish a draft PR/A handoff. No installation/activation.

## Ledger

Base019d6c7 explicitly named in A agreement6563512653. API agreement unblocked after
the prior turn; #149 pure producer is queued without partial implementation. Existing
M UI/host branches remain intact; latest A#153 integration is reviewed separately.

Executed: initial RED for the missing factory keyword;53focusedPASS plus1raw-ASGI
PASS,365NodePASS,full1190backendPASS/zero skips/2existingwarnings/1687.78s.
Unknown-scan expectation was corrected to the existing Store401; no authorization
behavior changed. Fresh read-only review found no remaining findings. Scoped #153
integration/CI and #152 consumer reviews are recorded in the stage. Final publication
and exact commit are recorded in the claimed issue/PR; no installation/activation.
