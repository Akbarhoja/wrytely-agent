# Canvas course page implementation plan

> **For agentic workers:** Use superpowers:executing-plans with TDD for this single increment.

**Goal:** Read one bounded, validated course metadata page for the resumable collector.

**Architecture:** Add `coursePage(cursor = null)` to the existing `makeReader`, sharing its transport, stream limit and Link parser. Keep legacy `get/list` behavior compatible. Return raw bounded rows and a validated opaque continuation; mapping and checkpoint persistence remain in the collector increment.

**Tech stack:** Native JavaScript, Fetch, Node tests; no new dependencies.

**Spec:** [claim #100](https://github.com/Akbarhoja/wrytely-agent/issues/100), [work order P1-M1](../../WORK-ORDERS.md).

## Global constraints

- M-owned reader/tests/docs only; no shared Store, CI, STATUS or installed diagnostic edits.
- Base own tested `1e294753`; branch `codex/canvas-course-page` in existing isolated worktree.
- GET, credentials include, redirect error, no-store, 15-second signal, 1 MiB streamed body, at most 50 object rows.
- Exact HTTPS Canvas origin and `/api/v1/courses`; only active enrollment, per_page=50 and one optional opaque page parameter.
- Strict UTF-8, exact final response URL, HTTP200, bounded complete Link parsing, at most one next relation and no direct self-cycle.
- No real Canvas access, extension installation, auth grant, send, provider spend or deployment.

## Task 1: reader and verification

- [x] Write `extension/canvas-feasibility/page.test.mjs` covering valid continuation, one-request limit, unsafe persisted cursor, redirect/final URL, body/type/count/UTF-8/header limits, failures and malformed/duplicate/cyclic links.
- [x] Run tests: expect missing `coursePage` failure before implementation.
- [x] Extend `probe.mjs`, factoring the existing Link parser; preserve legacy diagnostic behavior.
- [x] Run new and existing Node suites: expect all pass, no skips.
- [x] Run Ruff check/format and full pytest on disposable PostgreSQL, web/typecheck, changed-file Prettier and diff checks: expect pass.
- [ ] Review the whole delta, document actual limits, commit/push draft PR referencing #100; request A-owned CI inclusion and counterpart review.

## Review focus

- A real Canvas continuation may use an unsupported query variant: return a visible controlled error, never silently finish.
- Legacy diagnostics must retain their existing pagination behavior.
- Malformed non-next relations must not hide the next page.
- Transport timeout must also bound streamed reads, not just initial headers.
- Raw provider content and cursor remain private intermediate values, never diagnostic output or public evidence.
