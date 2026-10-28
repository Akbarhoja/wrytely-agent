# Murtazo — integration handoff

Owner: `murtazokhon-tech`. Start here, then read [the plan](../BUILD-PLAN.md),
[TEAM.md](../../TEAM.md), [STATUS.md](../../STATUS.md),
[CONTRACTS.md](../../CONTRACTS.md) and [web setup](../../web/README.md).

## Start from the implemented baseline

```sh
git clone https://github.com/Akbarhoja/wrytely-agent.git
cd wrytely-agent
git switch codex/team-integration
git pull --ff-only
git switch -c murtazo/whatsapp-delivery
```

Use `codex/team-integration` as the PR base until the combined baseline lands on
main. Extend existing code. Do not create a second frontend, database client,
authentication system or agent runtime. See TEAM.md for review/merge rules.

## First PR: official WhatsApp delivery

The adapter, signature verification, verified linking, inbound task persistence
and reply outbox already exist. See [WhatsApp setup](B1b-whatsapp.md).
Akbar confirmed the Meta app/test number is not set up yet. Prepare the code and
tests while coordinating development credentials securely with him.

Deliver a durable outbound worker that claims queued replies, checks current
number ownership, pause/cancellation and permitted delivery timing before sending,
records provider acceptance accurately and handles ambiguous sends without blind
retry. A restart after sending must not silently duplicate delivery. Agree schema
and concurrency changes with Codex before implementing. Add authenticated provider
status handling with valid state transitions. Replayed/out-of-order callbacks must
not regress delivered state or affect another account.

The adapter is text-only. Implement conversation-window enforcement and approved
templates for proactive messages before promising unrestricted follow-ups. Quiet
hours require persisted timezone/preferences; coordinate those fields. If a required
permission/window/preference is unknown, hold delivery with a visible reason.
Use official Cloud API, not a personal-account bridge.

Acceptance: offline transport/storage tests cover lost responses, repeated claims,
pause/unlink, expired conversation windows, webhook replay and restart. A separate
live development smoke test uses consenting test numbers and a real Meta-powered
reply. No real classmates or instructors are contacted without explicit approval.

## Second PR: onboarding and account/WhatsApp connection controls

Extend the existing Next.js/Clerk scaffold. WhatsApp is the student's primary
communication channel. Website: signup, connections, academic context, results,
status and controls. Keep the existing work-first overview; do not make a new
chat-first homepage. Add verified link/status/unlink controls and the necessary
same-origin backend proxy allowlist. Keep link codes out of logs/analytics.

Prove two independent test students have separate agents, phone mappings and saved
results; logout/re-login restores the same agent. Session expiry, backend failures,
limits and retry uncertainty must preserve useful student work. Reuse existing
Clerk development settings, not production keys or a new replacement app.

## Third PR: initial course/group context

Choose one approved source path with Codex. Supply versioned observations with
stable IDs, evidence and actual coverage. Use synthetic fixtures if institutional
access is unavailable, labeled clearly. An uploaded snapshot is not ongoing Canvas
monitoring. Review institutional permissions/platform terms before connecting.
The runtime planner already supports internal responsibilities; coordinate how an
explicit student delegation reaches its trusted store interface. Source memory,
policy checks and artifact verification belong to Codex’s runtime track.

## Every PR includes

- Concrete behavior and edited interfaces; mention planned shared-file edits early.
- Relevant test commands/results, screenshots when UI changes, known limitations.
- Clear separation of offline tests from real provider evidence.
- No credentials, personal course records or fake claims of completed integration.

Do not modify the current Wrytely product or deploy/migrate its production services
as a side effect. Akbar owns release approval and credentials; Codex reviews
integration and coordinates the shared runtime/contracts.
