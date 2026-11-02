# Wrytely academic agent

A new personal academic agent powered by Meta models. Built separately from the
existing Wrytely handwriting product for the Meta Global AI Developer Hackathon.

## Current implementation

The P1 completion candidate on `codex/p1-completion` connects the existing Canvas
extension to document storage and a student connection/coverage interface. It
collects discovered courses, assignment instructions/rubrics, syllabus text,
announcements, discussion threads/replies, modules/items, pages, own submissions/
feedback, assignment grades and readable course files. PDF support extracts text;
images, restricted or external content and unsupported formats remain explicit gaps.
Students can choose course/content scope, inspect coverage and disconnect. Manual
snapshots remain troubleshooting, not the normal connection flow.

Existing foundations include Clerk sign-in, a private agent per verified account,
scoped Postgres memory, durable bounded Meta tasks, explicit delegation and checked
private drafts. Document-based saved drafts now have an explicit v2 inspection view
with pinned original evidence and current access checks. Saved checks do not grant
permission to send or submit work.

**P1 is not complete yet.** Local synthetic integration checks are separate from
installed Chrome and live two-course acceptance. The new candidate has not been
deployed; the existing isolated development service still runs the older M2 build.
Independent review/CI and protected-main merge status remain separate. See
[the P1 candidate and live checklist](docs/P1-COMPLETION-CANDIDATE.md),
[STATUS.md](STATUS.md) and [work orders](docs/WORK-ORDERS.md).

Continuous semester supervision and follow-through are later P2–P6 work. Development
model and WhatsApp workers stay stopped outside separately authorized tests; no
completed 24/7 academic agent is claimed. WhatsApp live-delivery acceptance remains
open. Outlook email is optional and paused; Teams, handwriting and Hermes are outside
the first-version scope. The existing handwriting product and its production
configuration are not changed by this repository.

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

The source repository is public at https://github.com/Akbarhoja/wrytely-agent.
The MIT license covers this repository's code. Connected services and any future
model weights remain subject to their own terms.

Murtazo is the integration/web/source owner and an existing contributor. Codex
owns runtime/shared contracts and integration review. All feature changes use
scoped claims, PRs, contract checks and counterpart review; see TEAM.md and the
pinned coordination issue. Independent human review is required for protected-main
integration. Do not treat assistant review through the same GitHub account as
that approval.

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

Public pilot launch still requires cumulative usage reservation/limits, live
acceptance evidence, connector permissions and operational validation. Existing
authentication, private artifact reads and delivery controls have code/test evidence;
that does not establish production readiness or successful live delivery.

## Web development

See [web/README.md](web/README.md) for the Next.js app, auth setup, same-origin API
boundary and the live acceptance checks. Its unconfigured public shell works
without credentials and cannot access private data or send work to an agent.
