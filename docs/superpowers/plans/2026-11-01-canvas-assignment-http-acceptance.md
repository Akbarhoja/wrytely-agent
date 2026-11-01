# Assignment HTTP acceptance implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline; one fresh whole-branch reviewer, no implementation delegation.

**Goal:** Prove the existing paired assignment client interoperates with the existing private academic routes and disposable Store.

**Architecture:** Extend existing M-owned Node loopback driver and Python fixture/assertions. No production behavior change or new store/fixture module. Synthetic already-extracted assignments go through the real mapper/journal, HTTP DTOs and Store transactions. The parent asserts durable state independently of the driver.

**Tech stack:** Node24+, pytest/FastAPI/Uvicorn, disposable local Postgres.

**Spec:** [#115](https://github.com/Akbarhoja/wrytely-agent/issues/115), existing C2v1, own #114 exact47d076d; branch `codex/canvas-assignment-http-acceptance`.

## Constraints and ownership

- Exact four files: existing `extension/canvas-pairing/http-interop.mjs`, `tests/test_canvas_discovery_client_http.py`, this plan and scoped stage doc.
- Standing M sole-editor agreement #4/6548726117,6548849672 and P1 cross-layer ownership6548991501; fresh claim6552289221. No conflicting claim or new shared interface. The earlier request6552265282 does not revoke that existing assignment.
- Preserve10oldactual scenarios, strict environment whitelist, loopback-only dispatch, suppressed private errors and bounded child output. No missing-Node skip.
- No source fetch/parser/live data, external send, provider spending, auth/production change, install/host/scheduler/activation. Chrome untouched/open and automationoff.
- Required focused plus full disposable backend/Ruff/format and Node/web/type checks; CI/counterpart remain separate.

## Task — actual assignment transaction acceptance

- [x] Add seven parent scenario names/assertions; observe RED because old driver rejects unknown scenarios.
- [x] Extend existing driver for two assignment pages/close, before/after loss and resume, partial evidence, scope/revoke races and cross-account denials. Keep captured key/body exact except explicit lease rebase.
- [x] Assert parent Store row/receipt counts, correct course/assignment/provenance/content, staged/unpromoted versions, exact manifest/coverage, no writes on denial. Run focused17actual scenarios GREEN.
- [ ] Run required full checks on disposable Postgres; fresh read-only review and fixes; scoped evidence docs, draftPR and Akbar handoff.

## Review focus

- Loss is injected after actual HTTP commit, not a fake server receipt; recreated client uses the same persisted journal and exact pending key/body.
- Scope/revoke races run after client validation but before real Store mutation and leave zero assignment versions/observations.
- Partial early evidence cannot become complete through a later complete page; test both local denial and direct HTTP denial.
- Cross-account bearer must not authorize Alice's captured scan; legitimate recovery must still work without changing the captured body.
- Database assertions prove exact immutable/source/receipt count and no promotion; child success alone is insufficient.
