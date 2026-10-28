# Engineering status

Started October 27, 2026. Supervisor: Akbar. Lead: Codex. Engineer: Murtazo.

| Stage | Owner | State | Evidence / remaining work |
|---|---|---|---|
| P0 existing-service inspection | Codex | partial | Existing product uses Clerk Next.js 7, Neon/Postgres, S3-compatible storage; no production changes. Live account configuration pending. |
| S0 foundation | Codex | in review | Isolated repo, scoped Postgres migration, auth verifier, provisioning, durable queue, bounded Meta adapter and API. Offline tests against real local Postgres pass. |
| A1 task/worker foundation | Codex | in review | Attempts fenced, same-agent concurrency controlled, pause/restart behavior tested. Full planner and stateful episode resumption still to build. |
| B1a signed-in frontend | Codex scaffold; Murtazo live integration | scaffold in review | Next.js workspace, Clerk routes/provider, authenticated same-origin API boundary, persisted retry keys, task status and pause controls. Live two-account checks pending. Akbar will invite Murtazo. |
| B1b verified messaging | Murtazo | not started | Requires selected provider access and expanded delivery/linking contracts. |
| M1 live round trip | Both | not achieved | Need isolated database configuration, existing Clerk instance public verification configuration, Meta development key, frontend and messaging integration. |
| M2 academic ownership | Codex + Murtazo | not started | Responsibilities, assignment context, self-directed planner, artifacts and checks. |
| M3 public pilot | Both | not started | Usage budgets, connectors, controls, external-action gateway and integration evidence required. |

No live Meta or Clerk call has been verified. No public signup or deployment is
enabled. No customer database migration was applied. The current model tests are
scripted provider responses against a real disposable Postgres store. Web tests
use injected sessions and simulated HTTP responses. Public-shell browser checks
do not establish a live authenticated round trip.

The GitHub repository is now public at Akbar's request. The application itself is
not deployed publicly. Existing Wrytely production configuration is unchanged.

Current local verification: 44 backend tests against disposable Postgres and 24
frontend boundary/interaction tests pass. Ruff, Prettier, TypeScript and the Next.js
production build pass. Browser checks cover 1440px desktop and 390px phone views,
connection navigation and no horizontal overflow. Main branch protection is verified
as described in TEAM.md. Live provider integration remains unverified.

The default student screen is now a work overview, with conversation as a separate
view. Its account-scoped task list reads the latest 50 real records and refreshes
without opening chat. No sample course work or decision requests are populated.
Current saved tasks are conversation tasks; academic responsibility ingestion,
decision requests and autonomous course workflows remain future implementation.

October 28 continuation: B1b WhatsApp adapter preparation is implemented locally:
raw-body signature validation, business/number filtering, text extraction and a
single-attempt sender with accepted/failed/unknown outcomes. Ten new offline tests
pass. No live WhatsApp request was made. No webhook route or automatic sender is
enabled; durable linking, inbound deduplication, outbound storage, status callbacks
and template/window enforcement remain required. DBOS is still a proposed bounded
trial, not an adopted dependency.

Validation for this continuation: all 54 backend tests pass against disposable
local Postgres; Ruff lint and formatting pass. Dependency lock updated. Existing
24 frontend tests were not rerun because no frontend code changed.

October 28 B1b continuation: development webhook routes and authenticated
link/unlink APIs now persist single-use expiring challenges, verified numbers,
unique inbound provider IDs, text tasks and a transactional reply outbox. Link
secrets do not enter model context. Unlink cancels pending delivery and relinking
does not redirect old work. Migration 002 is local-only; existing migration 001
is unchanged. A concurrency test exposed a pre-existing task-claim race; a fresh
active-lease check under the agent lock now prevents overlapping worker claims.

Validation: 62 backend tests pass against disposable local Postgres; Ruff lint,
format and diff checks pass. No frontend files changed. No live credentials,
WhatsApp sends or production migrations were used. Delivery worker, web linking
controls, delivery callbacks and template/window enforcement remain unfinished.
Development setup is documented in docs/stages/B1b-whatsapp.md.
