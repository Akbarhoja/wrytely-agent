# Canvas client-to-HTTP acceptance plan

> **For agentic workers:** Use superpowers:executing-plans and test-driven-development.

**Goal:** Verify the actual Node discovery client/journal against actual FastAPI routes and disposable Postgres transactions.

**Architecture:** Pytest owns a loopback-only ephemeral Uvicorn service using existing synthetic Store/SessionVerifier fixtures. A bounded child Node process drives actual client methods; fixture-only fetch translates a configured HTTPS test origin to loopback HTTP and preserves the client-facing response URL. This tests serialized contracts/auth/receipts, not production TLS or browser networking. Production code and auth checks remain unchanged.

**Spec:** [Claim #102](https://github.com/Akbarhoja/wrytely-agent/issues/102), A single-editor agreement [#96](https://github.com/Akbarhoja/wrytely-agent/pull/96#issuecomment-6548725324).

## Constraints and interfaces

- Base reviewed A CI-only #101 `fec20562`, containing exact M #96. No edits to app/shared/contracts/runtime/CI/STATUS; only tests/test_canvas_discovery_client_http.py, extension/canvas-pairing/http-interop.mjs and scoped plan/handoff.
- Existing synthetic session verifier only; generated pairing/bearer/lease credentials remain in process memory. Child config via stdin, minimal OS env only, no provider/production envfiles, NODE_OPTIONS or token arguments/logs.
- Bind127.0.0.1 port0; never expose fixture service externally. Disable access logging. Own socket/thread/child cleanup; no Chrome/service intervention.
- Fault injection belongs only to fixture middleware/transport: lost acknowledgment before/after server commit, expired lease, scope/revoke race. Actual API authorization and Store fencing still decide outcomes.
- Assert real catalog/receipt/resource state and no academic source activation. Missing Node is a failure, not skip. Fixed child pass/phase/code summaries only.

## Task: actual boundary scenarios

- [x] Write Python scenarios/assertions; observe absent harness RED.
- [x] Implement Node driver reusing the actual private client, in-memory trusted storage and synthetic refusing Canvas profile reader.
- [x] Pass lostack/restart/replay, replaced/expired lease, partial finish, scope/revoke and cross-account cases against actual Store.
- [x] Run full required disposable backend/Ruff/format, Node suites, web/typecheck, formatting/diff and read-only review.
- [ ] Publish coherent draft PR and handoff exact scoped/live/CI limits to A. #100 collector remains planned until this boundary is established.

## Execution record

A agreement6548725324 and claim102/#4comment6548815483 precede fixture edits. Initial missing-driver RED reproduced. Focused actual run7pass/1fixtureassertion failure: per-generation catalog history intentionally has two rows for one provider course. Corrected assertion only; final8pass12.40s. No product implementation change. Full673backend passed/two warnings/385.79s on fresh disposable Postgres, unchanged119Node/no skips,114web/32.69s,TypeScript/Ruff/formatting/diff passed. Read-only fixture review no blockers/no independent test rerun. Node24 prerequisite in foundation requested from A in6548881096, no M workflow edit. A#98 source-fix review remains independent from this metadata base.
