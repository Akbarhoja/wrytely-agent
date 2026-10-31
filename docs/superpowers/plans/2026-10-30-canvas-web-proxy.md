# Private Canvas web proxy implementation plan

> Execute inline with test-driven-development; reuse the existing forwarding boundary.

**Goal:** Let verified web sessions consume accepted Canvas lifecycle routes.
**Architecture:** Extend only the explicit private route allowlist and bound new Canvas
POST request streams before forwarding. No new auth system, endpoint, UI or dependency.
**Spec:** P1-M1/P1-M3 in WORK-ORDERS; implemented #64 lifecycle handoff; claim #67.
**Base:** bdb0e89 (#66), existing isolated worktree.

## Global constraints

Only POST source-connections/canvas/pairing, GET source-connections/UUID and POST
source-connections/UUID/revoke. Match actual path segments, not encoded slash joins.
Reuse Clerk/session verification and same-origin POST checks. Browser owner/auth/cookie
headers never become upstream authority. Keep redemption/bind/scope/sync inaccessible
through this proxy. New Canvas POSTs have a16KiB actual streamed-byte cap; stop reading
at overflow, cancel the reader, forward nothing. Invalid UTF-8 yields controlled422;
stream/upstream failures stay generic503/no-store. Existing non-Canvas routes unchanged.

## Task 1: Private lifecycle forwarding

Files: web/lib/forward.ts; web/tests/canvas-forward.test.ts;
docs/stages/P1-CANVAS-WEB-PROXY.md; this plan. Consumes only the existing #64 endpoints.

- [x] Add focused route/method/auth/origin/header/traversal/stream/upstream tests.
- [x] Run RED; implement minimal exact routing and Canvas-only bounded body read.
- [x] Run focused/full web tests and TypeScript; required backend/Ruff checks.
- [x] Independent read-only review, draft PR and Akbar counterpart handoff.

Review focus: embedded slashes in catchall segments, fake Content-Length, streamed
overflow with trailing unread data, cancellation errors masking413, and upstream errors
echoing secrets. No live provider access, private course evidence, deployment or migration.
Chrome stays open. Shared scope/device-context and PDF dependencies remain separate gates.

Evidence: initial focused31 cases had17 RED and14 denial checks already green.
After implementation and six added boundary cases, full web151 pass and TypeScript
pass. Required backend550 pass on disposable Postgres; Ruff check/format, Prettier
and diff checks pass. Reviewer found no blocker and independently probed the stream
and route boundary; reviewer Vitest was blocked before collection by sandbox EPERM.
Counterpart review, integration, UI and deployment remain pending.
