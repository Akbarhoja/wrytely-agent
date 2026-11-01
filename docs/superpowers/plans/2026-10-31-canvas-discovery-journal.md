# Durable Canvas discovery transport plan

> **For agentic workers:** Use superpowers:executing-plans and test-driven-development.

**Goal:** Preserve worker discovery intents and checkpoints across suspension and lost backend responses.

**Architecture:** Reuse the existing pairing client's private credential, context/profile reads, bounded transport and per-storage operation lock. Add discovery.mjs for the journal state machine; optional discovery state lives in the same atomic trusted-context pairing record. Re-pair/cleanup removes it with the credential. No token getter or separate store/router is introduced.

**Spec:** [Claim #95](https://github.com/Akbarhoja/wrytely-agent/issues/95), implemented C1/C2 and #94 HTTP handoff. Branch codex/canvas-discovery-journal starts at8bc90b0.

## Interfaces and constraints

- Worker-only beginDiscovery/resumeDiscovery/commitDiscoveryPage/finishDiscoveryResource/finishDiscovery/retryDiscovery/readDiscoveryStatus. Metadata only; no provider-content collection loop.
- Persist exact key/capture/expected checkpoint before dispatch, validate/persist acknowledgment before result. Unresolved intent cannot be replaced by another operation. No implicit retry loop.
- Resume has its own durable key, retains pending primary operation and may replace only its lease. A pending begin must first be replayed to discover scan ID. Explicit retry uses the same captured body/key; Store supplies idempotency. Unexpected remote advancement stops instead of inventing counts.
- Validate journal binding (connection/generation/scope/profile), course envelope<=1MiB, <=50/page, <=100pages, <=5000 total, checkpoint cursor<=4000 Unicode code points. Journal/finish-only reply<=8MiB, other discovery replies<=2MiB; retain initial plus discovered scan resource membership up to54001 keys. Support all required kinds and scope sizes; no academic completion.
- Fresh existing context/profile bracket mutation and result. Credentials/lease never returned. Worker checkpoint can contain private cursor for the future trusted collector; read-only status omits cursor, subject, source text and secrets. No UI/content-script bridge here.
- Same-worker/realm lock and atomic record write only; no cross-realm transactional storage guarantee. Store fences concurrent writers; installed host must own one journal writer.
- Edits only client.mjs, new discovery.mjs/discovery.test.mjs and this plan plus scoped handoff. No app/shared/contracts/runtime/STATUS/CI/dependency changes, live access/grants/sends/spend/deployment or automation restart.

## Task: durable worker transport

- [x] Write synthetic restart/loss/replay/lease/storage/control/bounds tests and observe absent-method RED.
- [x] Implement protected journal and receipt projection using existing client helpers; focused GREEN.
- [x] Verify expiry/account/scope/revocation races, no pending overwrite, bounded malformed replies and finish coverage; read-only review/fixes.
- [x] Existing Node/web/typecheck, required locked Ruff/format/full disposable backend, formatting/diff and exact evidence.
- [ ] Publish draft PR and request A counterpart acceptance; distinguish mocked/scripted from installed/live operation.

## Execution record

#95/#4 comment6548391208 precede edits. Existing isolated worktree and same pairing record reused. Initial RED17 missing methods; first GREEN97 after correcting strict envelope construction. Final119 Node passed/no skips. Specific resume-rejection/Unicode/terminal-state/profile-expiry/retained-ledger/finish-receipt regressions first RED then GREEN. Review-driven capacity/membership ruling recorded before edits in#95 comment6548579542. Required unchanged backend665 passed/two warnings/370.29s on fresh disposable Postgres; web114 passed/33.68s; TypeScript/Ruff/formatting/diff passed. No Python/web source change. Reviewer independently confirmed fixes and seven focused cases passed, no remaining material finding in those deltas. Journal changes remain synthetic, not installed/live collection; CI and counterpart acceptance separate.
