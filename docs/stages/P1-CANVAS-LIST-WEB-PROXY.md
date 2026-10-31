# Private connection list web proxy

M-owned [claim #89](https://github.com/Akbarhoja/wrytely-agent/issues/89) closes the list API-to-web-proxy gap. Branch `codex/canvas-list-web-proxy` starts from reviewed #82 `f85ae75ad7ce396eea6cf8950ee767aa8d57616f` and reuses the unchanged #68 lifecycle proxy commit as `96ce330`. This combines existing M implementations without duplicating the backend router or shared Store.

`GET /api/agent/source-connections` now forwards to the existing `GET /v1/source-connections`. The existing server-verified Clerk session supplies the upstream token; browser authorization, cookies and user headers are excluded. Requests use no-store, redirect rejection, the existing 15-second timeout and one upstream attempt. Every response remains no-store, including rejected inputs and controlled failures.

Only one `limit` and one `cursor` are admitted. Limit is one or two ASCII decimal digits with numeric value 1–20; absence preserves the backend default of 20. Cursor remains opaque and is limited to 128 UTF-16 code units; the raw URL search including `?` is limited to 1024 code units. Unknown, repeated or out-of-bound fields return generic 422 after session verification, without reflecting input or contacting the backend. URLSearchParams reconstructs the upstream query; embedded separators cannot become additional fields, a path or a fragment. The backend still validates cursor syntax, existence and ownership with private 404. Empty or malformed bounded cursors are forwarded for that decision.

The exact one-segment GET route is permitted. Disguised paths, list POST and extension-only redeem/bind/sync routes remain unavailable through this proxy. Non-list lifecycle query stripping and other existing behavior are preserved. No new UI, HTTP backend method, shared contract, dependency or configuration is introduced.

## Evidence and handoff

Initial synthetic focused tests produced 33 expected missing-route failures and 40 passes before implementation. The first implementation then passed all 73 focused cases. With additional boundary, two-page and configuration cases, the final full web suite passed 191 tests across 10 files in 52.52 seconds using one worker. TypeScript, locked Ruff check/format and changed-file Prettier/diff checks passed. Full backend verification on a fresh disposable Postgres database passed 621 tests with two existing test-library warnings in 420.90 seconds. Read-only whole-slice review found no material finding; the reviewer did not rerun suites. Remote CI is separate from these local results.

The initial sandbox-only test attempt failed before collection because of a temporary-file rename restriction. A permitted normal-context retry supplied the RED/GREEN evidence. The default parallel full web run stalled and was stopped without a result; the final one-worker run kept every test enabled. No application or test configuration was changed to obtain that result.

Web checks use synthetic sessions and mocked upstream responses. Separate existing backend tests exercise actual private Store/API ownership, pagination and lifecycle on disposable Postgres. Those component checks do not prove deployed Clerk login, browser-to-Canvas collection, source readiness, installation, or live account access. No source-reader #86, course catalog/body consumption or PDF byte handoff is activated here.

Akbar's counterpart review and a consolidated integration baseline remain necessary. STATUS is left to its current A editor; the #4 handoff requests a bounded evidence update. No production migration, deployment, protected-main merge, provider grant/send/spend or private source publication is included. Chrome remains untouched; recurring automation was deleted at the user's request.
