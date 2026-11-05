# Fresh-clone local setup

Post-submission engineering instructions. This document does not deploy, grant
access, register a webhook, run a provider, apply retained migrations or authorize
spending. Preserve the submitted candidate/history. A owns runtime/shared/source
readiness and final integration; this M-owned guide covers the app/web/channel seams.

## 1. Select the reviewed code

```powershell
gh repo clone Akbarhoja/wrytely-agent
cd wrytely-agent
git fetch origin
git switch --detach origin/codex/telegram-final-integration
git rev-parse HEAD
```

Without GitHub CLI, use `git clone https://github.com/Akbarhoja/wrytely-agent.git`.
This is A's release-review branch, not protected main. Compare the actual SHA with
[PR182](https://github.com/Akbarhoja/wrytely-agent/pull/182) and its checks before
using it; a moving branch name is not an approved deployment. Feature candidates
such as the practice-file transport in PR186 have separate evidence and approval.
Default main can still be an early baseline. Submitted history and later work
remain distinct. For an isolated hosted entrypoint, use the
[judge-frontend handoff](JUDGE-FRONTEND-HANDOFF.md); this guide starts local services only.

Prerequisites: Git, Python3.12+, uv, Node24/npm and a separately designated disposable
Postgres for tests. CI uses Linux/Postgres18. Native Windows has known PDF
extraction/discovery failures because the bounded PDF child uses POSIX `resource`;
do not remove resource limits or call a partially passing Windows suite green.
Use a supported Linux environment/CI for full PDF acceptance.

```powershell
uv sync --locked
cd web
npm ci
cd ..
Copy-Item .env.example .env
Copy-Item web/.env.example web/.env.local
```

Copies contain empty/example fields only. Fill authorized development values locally;
never copy another product's environment or paste secrets into logs/chat/GitHub.
Reuse the approved existing Clerk development instance; do not create a new app.
No inference, database access or Telegram send is needed to install dependencies.

The Git, uv, npm and Python commands in this guide also work in a macOS/Linux
terminal. Replace the two PowerShell copy commands with:

```sh
cp .env.example .env
cp web/.env.example web/.env.local
```

Use separate terminal tabs for the API and web commands below; no PowerShell-only
environment assignment is required because uv explicitly loads the root `.env`
and Next loads `web/.env.local`. For disposable tests only, macOS/Linux uses
`export AGENT_TEST_DATABASE_URL='DISPOSABLE_TEST_DSN'` and
`export AGENT_TEST_ALLOW_RESET=yes`; PowerShell uses
`$env:AGENT_TEST_DATABASE_URL='DISPOSABLE_TEST_DSN'` and
`$env:AGENT_TEST_ALLOW_RESET='yes'`. Replace the DSN placeholder with the isolated
test target, never a retained or production database. These assignments authorize
that test database's reset only, not a deployment or service activation.

## 2. Configure only the needed services

| Service          | Configuration names                                                                                                                                                                                                                                                               | Independent requirement                                                                                                |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| API/session      | `AGENT_DATABASE_URL`, `AGENT_CLERK_ISSUER`, `AGENT_CLERK_JWT_KEY`, `AGENT_AUTHORIZED_PARTIES`                                                                                                                                                                                     | Isolated agent database; real matching Clerk session; exact browser origin                                             |
| Private web      | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `NEXT_PUBLIC_CLERK_SIGN_IN_URL`, `NEXT_PUBLIC_CLERK_SIGN_UP_URL`, `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL`, `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL`, `AGENT_API_URL`                                  | Web and API verify the same existing instance; backend URL stays server-only                                           |
| Canvas           | `AGENT_CANVAS_ORIGINS`, `AGENT_CANVAS_DOCUMENT_EXTRACTORS`                                                                                                                                                                                                                        | Exact approved origin and converters; paired owner; explicit course/category scope                                     |
| Telegram         | `AGENT_TELEGRAM_BOT_TOKEN`, `AGENT_TELEGRAM_BOT_USERNAME`, `AGENT_TELEGRAM_WEBHOOK_SECRET`                                                                                                                                                                                        | Correct bot identity, separate secret callback, one-use account link and explicit permissions                          |
| Model/supervisor | `AGENT_META_PROVIDER`, selected provider's `AGENT_META_API_KEY` or `AGENT_FIREWORKS_API_KEY`, `AGENT_META_MODEL`, `AGENT_META_MAX_OUTPUT_TOKENS`, `AGENT_META_REASONING_EFFORT`, `AGENT_META_BUDGET_KEY`, `AGENT_META_INPUT_USD_PER_MILLION`, `AGENT_META_OUTPUT_USD_PER_MILLION` | Existing cumulative budget/student grant, approved model/prices, source/control fences; no automatic provider fallback |
| Tests            | `AGENT_TEST_DATABASE_URL`, `AGENT_TEST_ALLOW_RESET`                                                                                                                                                                                                                               | Disposable database only; reset permission must be explicitly set to `yes`                                             |

Only the publishable Clerk key belongs in a `NEXT_PUBLIC_` variable. Bot, provider,
Clerk server and database credentials never go into the browser or extension.
See the root examples for current fields and [A's preflight](../docs/INSTALLATION-CHECKS.md)
for provider-specific compatibility. Do not reset existing liabilities to make checks pass.

## 3. Check locally before starting services

```powershell
uv run --env-file .env python -m runtime.preflight --profile api
uv run --env-file .env python -m runtime.preflight --profile telegram
uv run --env-file .env python -m runtime.preflight --profile supervisor
```

These default checks print names/fixed remedies, not values, and perform no network,
migration or inference. They do not prove valid keys or a working provider.
The optional `--database-check` opens a read-only migration-ledger transaction only.
Review the intended isolated target before requesting it. Missing migrations are
not permission to migrate a retained or production database. For a newly approved
disposable development database only, the explicit migration command is
`uv run --env-file .env python -m app.migrate`; the services never migrate at startup.
Current Telegram/preparation code requires the checkout's complete migration ledger,
including029–030. Never copy a production DSN into test configuration.

## 4. Run the API and private workspace separately

After setup/target review, use separate terminals:

```powershell
uv run --env-file .env uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd web
npm run dev
```

Open the loopback URL printed by Next. Its exact origin must match the authorized
party configuration. Sign in through the real Clerk development instance. Without
valid Clerk configuration the public shell may render while private actions remain
disabled; a static `options-preview.html` is not the running app. `/healthz` is
liveness only; neither it nor preflight proves collection/inference/delivery.
Do not change `skipProxyUrlNormalize` to work around auth failures; see
[web setup](../web/README.md). Starting the API/web starts no model or message worker.

## 5. Prepare the extension without silently activating it

From the repository root, replace the two origin placeholders with reviewed exact
HTTPS origins and choose a new output path:

```text
node extension/canvas-browser/prepare.mjs API_ORIGIN CANVAS_ORIGIN .local/canvas-packages/FRESH_NAME
```

The output path must not exist; do not overwrite an installed package. Preparation
builds local assets only. Installing/reloading, signing into Canvas, pairing,
verifying identity, choosing courses/categories and enabling collection are separate
operator actions under the approved source scope. Keep Chrome open; do not alter
another active collector/profile. Scope/coverage/collection results remain authoritative:
a build or successful pairing is not complete readable course evidence. See the
[package behavior](../docs/stages/P1-CANVAS-BROWSER-PACKAGE.md).

## 6. Link Telegram, then separately authorize any operation

In the signed-in app: Connections → Telegram → Create private link message. Open
only the configured bot or copy the exact private `/start` message. It is one-use,
expires after10minutes and must not be shared. A working secret-authenticated
`POST /webhooks/telegram` callback must already be registered by the authorized
operator; this guide does not register it or expose a local server publicly.
Refresh the app to confirm the server reports Linked. Linking grants neither
reply nor preparation permission. Save each permission/timezone/quiet hours explicitly.
`/stop` pauses the original agent and disables Telegram permissions. Unlink cancels
unsent actions; it does not undo an in-flight or accepted transmission.

Ordinary text enters the existing task queue only after linking/consent. A separate
existing runtime worker must complete it; a separate Telegram worker must dispatch
its authorized result. A course-service pass uses stored source evidence and may
save preparation. Do not start any of these paid/send-capable processes merely
because the UI is linked. See [service separation](ONE-COURSE-SERVICES.md) and
[bounded Telegram assembly](TELEGRAM-ASSEMBLY.md). A concrete live approval specifies
candidate/environment, data/recipient, budget/attempt limit and stop/reconciliation.
Current reviewed code supports explicit `/accept OFFER_UUID`, `/decline OFFER_UUID`,
`/file ARTIFACT_UUID` and `/revise ARTIFACT_UUID instructions`. These use trusted
linked-owner commands, replay receipts and the original source/control gates.
An accepted command is not completed work or proof of file receipt; current
checked artifact/one-use delivery authorization is required. Long checklist TXT
is not a checked coursework DOCX. Availability depends on the exact installed
backend and separately approved operation; do not assume a local UI activates it.
No alternative provider or unofficial WhatsApp bypass.

## 7. Verify and report the actual layer

Use a fresh disposable test database and no concurrent reset suite on it:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
cd web
npm run format:check
npm test
npm run typecheck
npm run build
```

Record exact revision, platform, passed/failed checks and scripted/live scope.
A failed/unknown model result stays blocked with held cost; a lost send receipt
fence reports unknown, not persisted acceptance. Refresh does not authorize retry.
Provider outage, missing grants, missing scope, stale sources, quiet hours, or
revoked consent are distinct blockers. Never print raw provider bodies, DSNs,
private source content or token-bearing URLs to diagnose them.
