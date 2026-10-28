# B1a — first work order for Murtazo

Owner: Murtazo. State: ready after foundation merge; no work claimed yet.
Update: Codex has begun a Next.js scaffold in `codex/student-workspace`. Review that
PR and use `web/README.md`; do not create a competing frontend. The work below
remains the live integration acceptance contract.
Goal: a new or existing Wrytely user signs in, gets one private agent and exchanges
messages through the deployed backend contract.

## Before starting

Akbar invites you to the repo. Read AGENTS.md, TEAM.md, CONTRACTS.md and STATUS.md.
Branch `engineer/b1-authenticated-web` from the merged foundation. Open a draft PR.
Coordinate the frontend stack and visual direction with the lead before installing
a framework. The backend remains Python/FastAPI. Existing Wrytely brand and the
academic agent experience guide the design; polish follows a reviewed direction.

Primary edit scope: `web/`, `integrations/`, `app/` assembly, `deploy/`, related
tests and your status line. Changes to contracts/shared code are welcome in a
focused reviewed PR; read any relevant code. Do not create new production Clerk,
database or storage accounts, or copy the old product's private code into this repo.

## Deliver

1. Reuse the chosen existing Clerk instance in development. Never use production
   keys in a local test, call `clerk init` to create a replacement app, or place a
   secret key in frontend code.
2. Provide signup/login/logout using Clerk's current supported SDK. On agent entry,
   call `POST /v1/bootstrap` using a session token; restore the same profile on return.
3. Build the initial authenticated conversation: submit with a fresh idempotency
   key, display queued/running/done/blocked states, and retrieve own results. Poll
   only while needed; do not present queued work as a completed response.
4. Add pause/resume controls, recoverable session-expiry handling and useful
   empty/error states. Do not invent course data or show seeded records as live.
5. Supply a minimal separate web deployment configuration; discuss worker hosting
   with the lead. No automatic deployment into existing Wrytely production.

## Acceptance evidence in PR

- Two different test accounts each see one distinct agent and private messages.
- Refresh and re-login preserve agent identity and saved work.
- Another account's task ID returns 404; unauthenticated requests fail.
- A retry after a lost response reuses the same idempotency key, creating one task.
- Session expiry prompts sign-in without discarding unsent content or granting access.
- Own pause/resume works. Backend unavailability is shown honestly.
- Offline frontend/contract checks pass; a live development smoke test is clearly
  labeled with credentials omitted and no real student data.
- Screenshots/video of the actual flow and a list of remaining limitations.

## Next stage, not part of B1a

B1b adds WhatsApp if platform access works, or Telegram fallback. First agree a
verified channel-linking challenge, durable inbound ID, signature verification,
delivery queue and uncertain-send behavior with the lead. Never send messages to
real classmates/instructors during development without explicit authorization.

## How the lead reviews your work

Codex inspects your PR diff, runs the relevant tests, checks auth and data ownership,
and exercises the full request → queue → worker → result path. An adapter passing
its own fake tests does not substitute for the integrated test. Akbar receives the
review outcome before any critical change reaches production.
