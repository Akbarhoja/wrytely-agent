# Private connection list web proxy implementation plan

> **For agentic workers:** Use superpowers:executing-plans and test-driven-development.

**Goal:** Make the reviewed private connection-list API reachable through the existing web proxy.

**Architecture:** Reuse #82's API and #68's proxy without creating another router or store. Admit the exact one-segment GET route; validate and reconstruct only bounded pagination query parameters after verified session checks. Backend ownership checks remain authoritative.

**Tech stack:** TypeScript, Fetch, Vitest, existing FastAPI/Postgres tests.

**Spec:** [Claim #89](https://github.com/Akbarhoja/wrytely-agent/issues/89), existing C1 list in CONTRACTS.md and P1-M3 in WORK-ORDERS.md.

## Constraints and review focus

- M-owned branch `codex/canvas-list-web-proxy`, base #82 `f85ae75`, unchanged #68 reused as `96ce330`.
- Edit only `web/lib/forward.ts`, `web/tests/canvas-forward.test.ts` and this plan plus the scoped stage handoff. STATUS remains serialized by A.
- Existing server session supplies authority. Browser cookies, bearer and user headers cannot change the upstream owner.
- Exact GET path only. One ASCII decimal limit of one or two digits, numeric range 1–20; one opaque cursor of at most 128 code units. Query string capped at 1024 code units before parsing. Unknown or repeated fields return generic no-store 422 after auth, without forwarding/reflection.
- Cursor syntax, existence and ownership remain backend decisions, including private 404. Reconstruct URLSearchParams to prevent query/path injection; no raw query concatenation.
- No-store, timeout, redirect rejection and exactly one upstream attempt remain intact. No UI/provider/auth/dependency/schema/deployment changes or live evidence claim.

## Task: Close the list API-to-proxy gap

- [x] Add tests for empty/bounded pagination, query rejection, opaque encoding, verified authority, separate accounts, controlled errors, route disguises and no retry. Remove the old unsupported-list expectation.
- [x] Run focused Vitest and observe failures from the absent list route.
- [x] Admit exact GET list and implement bounded query reconstruction; rerun focused tests.
- [x] Run full web suite, TypeScript, changed-file Prettier, Ruff check/format and full backend suite against fresh disposable Postgres. Record scripted evidence separately from real Clerk/browser/Canvas behavior.
- [ ] Review the complete branch diff, fix material findings, publish one draft PR linking #89 and request A counterpart review. Preserve human/main gates.

## Execution record

Claim recorded in #89 and #4 comment6547638830 before implementation. Existing isolated worktree reused; no other owner's branch or private root notes edited. Recurring automation deleted at user's request.

Initial RED: 33 expected failures and 40 passes; first GREEN: 73 focused passes. Final full web run with one worker: 191 passed across 10 files in 52.52 seconds, including added boundary/page/config cases. TypeScript and locked Ruff check/format passed. The default parallel web attempt was stopped after stalling without a result; sandbox-only first collection failed on a temporary-file rename, so verified runs used the permitted normal process context. Read-only whole-slice review found no material finding and did not independently rerun tests. Full disposable backend: 621 passed, two existing warnings, 420.90 seconds. Prettier and diff checks passed. Remote CI and opposite-owner acceptance remain separate.
