# Wrytely academic agent

A new personal academic agent powered by Meta models. Built separately from the
existing Wrytely handwriting product for the Meta Global AI Developer Hackathon.

## Current implementation

Foundation milestone: Python/FastAPI API, Clerk session verification, one private
agent per verified user, scoped Postgres storage, durable message/task queue,
bounded Meta Responses tool loop, pause/resume checks, attempt fencing and retries.

The academic planner, course connectors, signed-in frontend, messaging adapters,
artifacts and public pilot are **not implemented yet**. See STATUS.md for evidence
and TEAM.md for ownership. No external message sends or assignment submissions are
possible in this foundation. Test results do not imply live Meta/Clerk integration
has been verified.

## Setup

Requires Python 3.12 and uv. Install dependencies:

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

On macOS the test dependency `pgserver` starts and deletes a disposable local
Postgres database. On Linux, supply a disposable Postgres connection through
`AGENT_TEST_DATABASE_URL` and set `AGENT_TEST_ALLOW_RESET=yes`. This permits tests
to truncate the `wrytely_agent` schema on that database. Never point tests at the
existing product database. CI supplies its own Postgres service and no API secrets.

## Configured development run

Copy `.env.example` to ignored `.env` and configure authorized development resources.
Do not paste keys into chat or commits. This program does not automatically load
an existing product's environment files.

- `AGENT_DATABASE_URL`: intended isolated Postgres database during development.
- `AGENT_CLERK_ISSUER`, `AGENT_CLERK_JWT_KEY`: existing Clerk instance issuer and
  public verification key. A public key is sufficient for initial verification;
  the backend does not need a Clerk admin secret. Update the key after rotation.
- `AGENT_AUTHORIZED_PARTIES`: exact allowed frontend origins as a JSON array.
- `AGENT_META_API_KEY`, `AGENT_META_MODEL`: Meta development key and available model.

After reviewing the target database, explicitly apply the additive migration:

```sh
uv run --env-file .env python -m app.migrate
uv run --env-file .env uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, run the persistent worker:

```sh
uv run --env-file .env python -m runtime.worker
```

Routes and semantics are in CONTRACTS.md. The frontend must obtain a real Clerk
session bearer token. There is no debug-user fallback or public test login.
`GET /healthz` is liveness; `/readyz` only reports configuration flags.

## Engineering review

Murtazo's first work order is `docs/stages/B1-murtazo.md`. All feature changes use
PRs, contract checks and integrated review. Akbar will invite him. No branch-rule
enforcement is claimed until the repository settings are configured and verified.

## Prior work and shared services

Existing Wrytely authentication, database/storage services, domain and hosting
accounts predate this event. This repository contains new academic-agent code and
agent-specific schema only. No existing private code or customer data was copied.
Handwriting, if later used, is a disclosed external tool. Reusing infrastructure
does not mean those services were created during the hackathon.

## Implementation references

- https://dev.meta.ai/docs/quickstart
- https://clerk.com/docs/guides/sessions/manual-jwt-verification
- https://neon.com/docs/connect/connection-pooling

Public pilot launch requires additional usage budgets, authentication/frontend
smoke tests, per-user connectors, artifact ownership, delivery controls and live
integration evidence. This foundation is not a production launch.
