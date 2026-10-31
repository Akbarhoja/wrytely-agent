# Private connection list implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Expose the reviewed private Store connection list through the existing HTTP router.

**Architecture:** Reuse the #64 router unchanged from57ca6eae, then add GET at its prefix. Pass only verified session ownership to the #71 Store method. No discovery or academic ingestion assembly.

**Tech Stack:** FastAPI, pytest, disposable Postgres, locked uv dependencies.

**Claim:** #80, coordination #4; base6237f1c. M owns the router and API tests. Store remains A-owned.

- [x] Add failing real-Store API tests in tests/test_source_connection_api.py for empty accounts, owned pagination and safe projection, authentication, generic cursor errors and invalid query rejection.
- [x] Confirm failure because GET at the router prefix is absent.
- [x] Add bounded query parsing and the Store call in app/source_connections.py; inherit private no-store/error handling.
- [x] Pass focused API tests, then required locked Ruff/format/full pytest. Use a disposable database only.
- [ ] Record actual evidence and limits in STATUS.md and docs/stages/P1-CANVAS-CONNECTION-LIST.md. Request counterpart review through one PR linked to #80.

No new frontend, collector, deployment, model/source activation or live provider test. Catalog/academic ordering defect remains A-owned and blocks those separate consumers.
