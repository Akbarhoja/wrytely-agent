# M1: prove the real student messaging round trip

New feature work is paused. This integration candidate combines existing runtime
through #16, Murtazo's delivery/connection controls through #20 and the template
contract #22. A4 #24 is parked and excluded. No protected-main merge without the
required independent review; no production changes are implied.

## Current evidence

Combined offline checks: 247 backend tests on disposable local Postgres; 44 frontend
tests; Ruff, Prettier, TypeScript and Next production build pass. These use injected
sessions/providers and are not proof of live auth, inference or WhatsApp delivery.

## Prerequisites — configure securely, never in chat or source control

1. Existing Clerk DEVELOPMENT instance: frontend publishable/secret keys and backend
   issuer/PEM public verification key plus exact authorized frontend origin.
2. Isolated development Postgres database (or a designated isolated development
   schema/branch), not Wrytely production; explicit migrations 001–007 only after
   confirming the target. No migration 008/A4 needed for this checkpoint.
3. Meta Model API development key and an explicit small live-test budget. The
   WhatsApp app token and model API key are distinct credentials.
4. Meta developer app with WhatsApp, test business account/phone ID, app secret,
   access token, explicit supported API version and public test destination number.
5. Consenting verified test recipients and public HTTPS backend webhook endpoint.
   Configure webhook verification token separately from the app secret. No tokens
   in URLs, messages, screenshots, logs or PR evidence. Avoid access logging webhook
   verification query strings.

Backend env names are in Settings/shared/config.py and .env.example; web names
are in web/.env.example. Backend Settings does not auto-load an env file; load the
intended development environment explicitly before starting processes. Read
web/README.md and docs/stages/B1b-whatsapp.md for existing setup. No auth bypass.

## Process boundaries

- Web: existing Next.js frontend with Clerk; AGENT_API_URL points at the backend.
- API: uvicorn app.main:app using the development configuration.
- Reasoning: python -m runtime.worker (Meta development key, same database).
- Delivery: python -m app.whatsapp_worker (Cloud API token, same database).
- Webhook: HTTPS /webhooks/whatsapp, signed POSTs and verification GET; Meta app
  subscribes to message events. Official development recipient restrictions apply.

Current delivery worker is text-only and supports_templates remains false, so
outside-window sends stay held even if template configuration exists. This is safe
for M1: a fresh inbound test message opens the reply path. Template wiring is
Murtazo-owned future integration and is not required to prove this text round trip.
No pretend provider approval is configured.

## Acceptance sequence

- Sign up/sign in with two real development accounts; each gets one private agent.
- Open connection controls; request a challenge and send it from the consenting
  student's test WhatsApp number to the configured business test number.
- Confirm the verified link and explicitly save consent/timezone/quiet hours.
- Send a harmless synthetic academic question to the business number; observe one
  saved task, a real Meta result, one authorized outbound action and actual reply.
- Inspect provider evidence: accepted is not delivered; record signed status data
  when available. Redact credentials and recipient identity in retained evidence.
- Verify the other account cannot access the first account's messages/task/link.
- Refresh and re-login restore the same agent; pause prevents new work/sends;
  restart preserves pending work; never blindly resend unknown deliveries.

Record exact commit, process/configuration provenance, test users (redacted), task
and delivery evidence and observed limits. Mark M1 complete only after the real
path succeeds. A checked graded draft is an A3 milestone, not required to claim
M1's basic live connection. Templates, Canvas/Teams, A4, release and wider public
signup remain separate checkpoints.
