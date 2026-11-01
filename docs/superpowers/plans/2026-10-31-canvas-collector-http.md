# Collector HTTP acceptance implementation plan

> **For agentic workers:** Use superpowers:executing-plans with TDD and one fresh whole-branch review.

**Goal:** Verify production collector orchestration through actual HTTP routes and a disposable Store.

**Architecture:** Extend the existing two approved fixtures, preserving their loopback and child isolation. Synthetic Canvas responses serve only the profile and two exact course URLs. The production collector drives actual pairing/scope/scan/batch/resource routes; Python checks the persisted result.

**Spec:** [#108](https://github.com/Akbarhoja/wrytely-agent/issues/108), explicit A editor agreement [6549371845](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6549371845).

## Constraints

- Base `4106dc88`; branch `codex/canvas-collector-http-acceptance`, existing isolated worktree.
- Only approved Python/Node fixtures and scoped plan/evidence docs. No product/auth/shared/CI/STATUS edits.
- Reuse actual loopback FastAPI/disposable PostgreSQL; no production database or provider network.
- Child OS-only environment and stdin config; fake credentials, profile and storage remain test-memory only. Fixed output schema and controlled errors; no source/cursor/token/stack output.
- No TLS, installed MV3, real Clerk or live Canvas acceptance claim. No live access/install/grant/send/spend/deploy/main merge; Chrome stays open.

## Task 1 — actual collector scenarios

- [x] Add two pytest scenarios and persisted assertions. Run only new cases: expect controlled configuration rejection before driver implementation.
- [x] Extend the existing Node driver with bounded fake course pages and production collector ticks, verified-session all_active scope with empty manual IDs, exact-body recovery after accepted acknowledgment loss, recreated worker and open academic resources. No manual discovery commit inside new scenarios.
- [x] Run all ten actual HTTP/Store scenarios: expect pass, two unique courses/two batch receipts per collector scenario, courses complete and two assignments open, active scan/checkpoint2 and zero source_versions/finish receipts.
- [x] Run full required Ruff/format/backend on disposable PostgreSQL,233 Node cases, web/TypeScript and formatting/diff checks; fresh review, fix justified findings with RED regressions and verify final state.
- [ ] Publish draft PR linking claim/agreement and hand off actual evidence/limits to A; request serialized STATUS/remaining CI gates, preserve incomplete P0/full academic/host gates.

## Review focus

- Never use a fixture-supplied manual course ID to drive the production collector.
- Accepted loss must cross the actual server commit before transport failure, with a stable saved intent on restart.
- Recovery must not request the first course page again or insert a third receipt.
- Academic rows remain open; no unsupported placeholder or aggregate finish receipt is accepted.
- Fixture adaptation must stay outside production code and deny all unexpected network targets without printing sensitive values.
