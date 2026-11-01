# Canvas discovery HTTP implementation plan

> **For agentic workers:** Use superpowers:executing-plans and test-driven-development.

**Goal:** Expose the agreed private scope and metadata-discovery Store operations through owned HTTP assembly.

**Architecture:** Add app/canvas_sync_api.py, register it from app/main.py, and reuse the existing CanvasRoute strict-body/error/no-store wrapper with its16KiB default intact. Scope and resource receipts receive64KiB for their full legal inputs; discovery batch requests receive a2MiB streamed HTTP cap while the existing Store still validates the serialized envelope at1MiB. DiscoveryBatch and Checkpoint remain the shared authority; no parallel transaction/lease/replay logic.

**Spec:** [Claim #93](https://github.com/Akbarhoja/wrytely-agent/issues/93), existing C1/C2 in CONTRACTS.md and P1-M1 in WORK-ORDERS.md. Branch codex/canvas-discovery-http starts at own #92 c1075bd on accepted A#84.

## Interfaces and constraints

- POST `/v1/source-connections/canvas/scope`: verified session, strict connection_id/generation/mode/course_ids/resource_kinds. Store derives/checks owner; missing owned connection stays private404.
- POST `/v1/source-connections/canvas/discovery/begin`: ingestion bearer, strict connection_id/generation/subject/scope_revision/begin_key.
- POST `/resume`: scan_id/generation/resume_key; POST `/batch`: scan_id/generation/lease_token/batch_key/expected_checkpoint/envelope (DiscoveryBatch only).
- POST `/resource`: scan_id/generation/lease_token/resource_key/finish_key/expected_checkpoint/outcome/reason. Complete only courses; selected academic resources may be honestly closed partial/restricted/unsupported while their collectors are unfinished.
- POST `/finish`: scan_id/generation/lease_token/finish_key. Existing Store controls every receipt, scope, generation, current subject, credential, lease, checkpoint, expiry and aggregate coverage.
- All discovery paths share the constant prefix above. No bearer, cursor, subject or provider reference in URL paths/query. Reject every query and unknown JSON field. UUID/replay keys validated; integers strict. Generic401/422/private404, controlled allowlisted409 codes, no exception/input reflection.
- New edits only app/canvas_sync_api.py, app/main.py, app/source_connections.py, tests/test_canvas_sync_api.py, this plan and one scoped stage handoff. Shared/contracts/runtime/STATUS/CI/dependencies unchanged.
- No academic upload or false source completeness. No collector scheduling, current-browser-account proof, live source access, grants/sends/spend/deploy/main merge. Context and sync remain separately authenticated snapshots/transactions.

## Task: private HTTP assembly

- [x] Add Store-backed API tests for full discovery/scope, replay/resume/fencing/partial state, auth/owner/control errors and streamed body bounds; observe missing-route RED.
- [x] Add strict DTOs, HTTP error mapping and thin Store calls; retain16KiB lifecycle/default controls, support64KiB scope/resource, and allow complete1MiB envelope wrapper; focused GREEN.
- [x] Verify interrupted/resumed/replayed and two-account scenarios; check redaction and prevent academic upload/completion.
- [x] Required focused/full disposable backend, Ruff check/format, existing Node/web/typecheck, formatting/diff; read-only review/fixes.
- [ ] Publish coherent draft PR linking #93 and request A counterpart acceptance; record exact local/CI/live limits.

## Execution record

#93 and #4 comment6548021502 recorded before edits. Existing isolated worktree reused. Prior PRs preserved; automation remains deleted and Chrome untouched.

Ruling recorded before implementation in #93 comment6548087454:16KiB would narrow legal1000-course and escaped4000-character checkpoint requests; permit64KiB only for scope/resource. Two regressions independently RED413 then GREEN. Initial route RED19->GREEN19; expanded focused64 passed. Final full backend665 passed with two existing warnings in368.88 seconds (all33 discovery cases included), existing Node80 passed/no skips, full web114 passed in31.07 seconds, TypeScript/Ruff/formatting/diff passed. Read-only review found no material finding; independent strict boolean check only, no DB/live rerun. No shared behavior replaced. Remote CI and counterpart acceptance remain separate.
