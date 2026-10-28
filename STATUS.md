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

Current local verification: 42 backend tests against disposable Postgres and 19
frontend boundary/interaction tests pass. Ruff, Prettier, TypeScript and the Next.js
production build pass. Browser checks cover 1440px desktop and 390px phone views,
connection navigation and no horizontal overflow. Main branch protection is verified
as described in TEAM.md. Live provider integration remains unverified.
