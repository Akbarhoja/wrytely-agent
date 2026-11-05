# Wrytely academic agent

A new personal academic agent powered by Meta models. Built separately from the
existing Wrytely handwriting product for the Meta Global AI Developer Hackathon.

## Current implementation and submission evidence

Wrytely is an owned Meta-powered academic-agent prototype, separate from the existing
handwriting product. The submission scope is one selected Canvas course. The Chrome
extension discovers courses and collects authorized originals; the cloud supervisor
chooses inspections, preparations, work offers or waiting from saved evidence. Closing
Chrome stops collection, so the agent cannot claim unseen course updates.

The live-tested backend is **7abbefc**; full CI41971364035 passed714 integration
and2164 backend tests plus web/build, extension and access. The release candidate
also includes M's separately reviewed timeout-status UI labels; its combined CI
is tracked in the release PR rather than inferred from the backend result.
It contains Clerk authentication, private account-bound memory,
resumable scoped Canvas collection, persisted supervision, a source-backed preparation
view, original checked-draft/revision/download machinery and the official Telegram
fallback. [Plan](docs/ONE-COURSE-DELIVERY.md), [status](STATUS.md),
[Telegram boundary/setup](deploy/TELEGRAM-ASSEMBLY.md).

Actual pilot evidence:

- Canvas discovered seven courses; the latest approved scan selected ECE253 only.
  The linked-file refresh saved25 assignments,27files and one syllabus. The target
  lab starter text is stored; its9-page manual has extracted text with explicit
  unread layout/image gaps. No claim of complete course or assignment readiness.
- The official Telegram bot is [@wrytely_agent_bot](https://t.me/wrytely_agent_bot).
  Real authenticated webhook pairing and a short inbound test message reached the
  existing task journal. Reply and proactive-preparation consents are separate.
- A real bounded course test reused stored ECE253 evidence, made two Meta inspection
  decisions and generated a source-backed preparation. Telegram accepted one send;
  the owner confirmed receipt. This used explicit JSON action mode on the same Meta
  model after native tool requests failed503. Earlier unknown reservations remain
  held. [Exact build, test and cleanup](docs/JSON-PREPARATION-DELIVERY-ACCEPTANCE.md).
  **Continuous operation and real checked-coursework file/revision receipt remain
  unproven.** Model and delivery workers are stopped after the bounded test.
- Existing draft, revision and Word-export acceptance evidence uses scripted models
  and synthetic sources. It must not be presented as completed real coursework.
  [Evidence and synthetic examples](docs/M-INTEGRATION-EVIDENCE.md).

The owned runtime uses Meta models; Fireworks serves Meta MuseSparkOpen via an
explicit adapter. The OpenAI SDK is an HTTP client, not the inference model.
[Provider boundary](docs/FIREWORKS-PROVIDER.md). The live-proven configuration uses
[explicit JSON actions](docs/FIREWORKS-JSON-ACTIONS.md), with the original runtime
validating/executing Meta's decisions. There is no automatic model/provider fallback.

Telegram replaces WhatsApp only for the disclosed submission fallback. WhatsApp
business verification remains pending. The development deployment supports ordinary
replies and preparation text/TXT plus explicit
`/accept`, `/decline`, `/revise` and checked-DOCX `/file` commands, offer notifications,
command acknowledgments and private command status. These use the compatible worker
and migrations031–032. Preparation receipt is live-proven; the real checked-file/
revision journey remains separate from its connected scripted acceptance evidence.
See the [academic delivery boundary](docs/contracts/TELEGRAM-ACADEMIC-DELIVERY-v1.md).
Current partial real-course evidence and unknown AI-submission policy do not authorize
graded drafting. Labs require the student's physical work and actual results.

The broader semester product, multi-course priority, Teams/group chats, calendars,
handwriting integration and long-term reliability remain roadmap work. Outlook is
optional and paused. Existing Clerk/database/domain infrastructure is reused as
agreed; the new agent code and isolated schema/development deployment are separate
from the prior handwriting product. [Privacy notice](docs/PRIVACY.md).
[Submission closeout checklist](docs/SUBMISSION-CHECKLIST.md).

For reproducibility, use this candidate branch or exact commit; public repository
visibility is not proof that protected main has received all reviewed candidates.
Required human review/merge protection remains in place.

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
- `AGENT_META_PROVIDER`: `meta` by default; explicitly select `fireworks` only for
  an authorized Fireworks run. There is no automatic fallback.
- `AGENT_META_API_KEY`, `AGENT_META_MODEL`: key/model for the Meta-hosted provider.
- `AGENT_FIREWORKS_API_KEY`: key for the selected Fireworks provider. That adapter
  fixes the model to `accounts/fireworks/models/muse-spark-open`; it does not use
  `AGENT_META_MODEL`, and it does not require a Meta-hosted key.
- `AGENT_FIREWORKS_ACTION_MODE`: explicit `json` is the live-tested action transport.
  Default `native` preserves native tool calling; there is no automatic fallback.
- `AGENT_META_REQUEST_TIMEOUT_SECONDS`: network timeout5–120 seconds, default30.
  The successful bounded preparation used90, low reasoning and4096 output tokens.
  This configuration does not activate a worker or grant a model budget.
- `AGENT_META_MAX_OUTPUT_TOKENS`, `AGENT_META_REASONING_EFFORT`: bounded output
  allowance (default2048; maximum16384) and optional reasoning effort. Reasoning
  counts against output tokens; the cost reservation uses the exact configured cap.
  Fireworks accepts unset/low/medium/high effort; other effort values are rejected.
  New settings do not authorize larger live calls or automatic retries.
- `AGENT_META_BUDGET_KEY`, `AGENT_META_INPUT_USD_PER_MILLION`,
  `AGENT_META_OUTPUT_USD_PER_MILLION`: trusted operator budget key and verified
  nonzero prices. Worker execution requires an operator-configured global budget
  and student grant; no credit balance creates an allowance automatically.

After reviewing the target database, explicitly apply the additive migration:

```sh
uv run --env-file .env python -m app.migrate
uv run --env-file .env uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For a secret-free configuration report, run
`uv run --env-file .env python -m runtime.preflight`.
It performs no network calls, inference, migrations or sends. An explicit
`--database-check` adds a read-only migration-ledger check. See
[installation diagnostics](docs/INSTALLATION-CHECKS.md) for profiles, exit codes
and what passing configuration does and does not establish.

The course supervisor and delegated drafting are separate entrypoints. The supervisor
reads stored course evidence and chooses inspect/prepare/offer/wait; acceptance is required
before the existing draft worker prepares work. For a separately authorized one-course
supervisor pass (with the current owner explicitly enrolled and its budget granted):

```sh
uv run --env-file .env python -m app.course_service --once --limit 1
```

This does not enqueue notifications by default and does not send WhatsApp messages.
For a separately authorized delegated academic execution pass:

```sh
uv run --env-file .env python -m runtime.worker --once
```

Routes and semantics are in CONTRACTS.md. The frontend must obtain a real Clerk
session bearer token. There is no debug-user fallback or public test login.
`GET /healthz` is liveness; `/readyz` only reports configuration flags.
The [service preparation](deploy/ONE-COURSE-SERVICES.md) describes separately
activated supervision and delivery processes; starting the API does not start them.

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

Public pilot launch still requires configured cumulative usage limits, live
acceptance evidence, connector permissions and operational validation. Existing
authentication, private artifact reads and delivery controls have code/test evidence;
that does not establish production readiness or successful live delivery.

## Web development

See [web/README.md](web/README.md) for the Next.js app, auth setup, same-origin API
boundary and the live acceptance checks. Its unconfigured public shell works
without credentials and cannot access private data or send work to an agent.
