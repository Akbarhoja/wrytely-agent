# Wrytely team agreement

Updated October 28, 2026. Shared plan: [docs/BUILD-PLAN.md](docs/BUILD-PLAN.md).
Actual evidence: [STATUS.md](STATUS.md). Shared interfaces: [CONTRACTS.md](CONTRACTS.md).

| Owner | Responsibility |
|---|---|
| Akbar | Product decisions, supervision, account access and release approval |
| Codex, supporting Akbar | Agent runtime, memory, planner, verification, shared contracts, integration review |
| Murtazo (`murtazokhon-tech`) | WhatsApp delivery, course/group source connections, onboarding, student website and deployment preparation |

GitHub write access for Murtazo was verified October 28. Existing scaffolds are
his starting point; Codex does not continue his implementation scope by default.
Shared-file fixes are welcome after coordinating the interface and edit scope.

## Shared baseline and branches

`codex/team-integration` contains all current implementation and the shared plan.
Until the reviewed integration baseline lands on `main`, both engineers branch
from `codex/team-integration` and target it with their feature PRs. Do not start
from the current minimal `main`, which does not yet contain the implementation.
The integration-to-main PR is the canonical combined baseline review; older PRs
1 and 2 are constituent reviews, not additional changes to merge on top of it.
After that baseline is merged, use `main` as the normal feature branch base.

- Murtazo: `murtazo/whatsapp-delivery`, then separate onboarding/source branches.
- Codex: `codex/academic-memory`, then separate verification/adaptation branches.
- Never push directly into the other engineer’s branch or rewrite shared history.
- Keep one coherent task per PR. Open a draft early and state files/interfaces
  being changed. Coordinate before editing shared contracts, schema or assembly.
- Pull the latest baseline before starting. Rebase/merge baseline updates into
  your own feature branch before final integration checks; do not force-push a
  shared integration branch.

## Review and integration

Codex reviews Murtazo’s diff for scope, ownership checks, tests and actual integrated
behavior, then reports findings to Akbar. Murtazo reviews Codex’s runtime PRs.
Codex uses Akbar’s GitHub account and cannot supply an independent approval of
Akbar’s own PR; Murtazo supplies that human approval after his review. Akbar
approves product or release decisions. Do not bypass protections to claim review.

Every PR states what changed, validation performed and remaining limitations.
Require relevant CI and an up-to-date integrated path before recommending merge.
For live integration, record redacted evidence and account isolation checks;
offline simulated responses do not prove the real provider works. Security or
permission-sensitive changes require focused review. No production migrations,
connector authorization or release is implied by an item existing in the plan.

Main protection was previously verified: required `foundation`, strict up-to-date
status, one approval and resolved conversations; force pushes/deletion disabled.
The `web` check should also be made required once its workflow lands. Akbar retains
the existing administrator override. The integration branch has no newly promised
protection; use PRs and the review procedure above.

## Lightweight daily coordination

Each engineer updates their task/PR with: completed work, next work, blockers and
any contract changes. STATUS.md records validated milestones, not aspirations.
Review one full end-to-end scenario together each day. Escalate missing provider
access early; continue independent code and tests while setup is pending.

Akbar can paste Murtazo’s PR URL into the Codex chat with “review this PR.” Codex
can inspect repository state when asked to continue, but does not monitor GitHub
between turns automatically. No scheduled monitoring or external messages have
been configured.

## Mandatory non-overlap rule

Each implementation task has exactly one owner and a GitHub issue claim BEFORE
coding: owner, branch, files, acceptance checks and dependencies. Other engineers
must read active claims before starting and cannot modify claimed files. Shared
files require an explicit agreement recorded in the coordination issue. Source
and messaging tests belong to Murtazo; runtime/store/planner tests belong to Codex.
The integration owner coordinates cross-layer smoke tests rather than creating a
second implementation. If a test touches both domains, agree its owner first.

Nobody takes over another's task due to delay or missing access. Only Akbar can
reassign scope, and his approval must be recorded in the issue before edits. A
request for review is not permission to rewrite the other engineer's branch.
Review feedback goes on the PR; its author implements fixes unless reassigned.

GitHub is the shared record, not separate chat histories. Use the coordination
issue for interface questions, blockers and handoffs; task issues for claims and
progress; PR comments for code review. At the start of each work session, check
new coordination comments, open PRs and active claims. At the end, post completed
work, next step, blockers, contract changes and exact validated evidence. Notify
@Akbarhoja or @murtazokhon-tech when their input is required. Codex may communicate
about this project through those GitHub issues/PRs under Akbar's authorization.
Do not expand that authorization to email, Discord or unrelated channels.

An unresolved contract change blocks dependent edits. Record a proposed payload,
ownership, error behavior and migration plan; obtain the affected owner's agreement,
update CONTRACTS.md, then implement. Resolve disagreements with Akbar.

CODEOWNERS routes review to the opposite engineer. It does not prevent writes;
strict scope is a repository rule enforced by each contributor/assistant and review.
Existing write access and main protection are unchanged. These rules do not create
an autonomous background watcher: Codex reads GitHub during active work sessions.

## Active GitHub coordination

- [Pinned team coordination thread — #4](https://github.com/Akbarhoja/wrytely-agent/issues/4)
- [Murtazo: WhatsApp delivery — #5](https://github.com/Akbarhoja/wrytely-agent/issues/5)
- [Codex: academic memory — #6](https://github.com/Akbarhoja/wrytely-agent/issues/6)

These work items are assigned and ready, not claimed as already in progress.
Each engineer posts the exact branch/file claim before starting implementation.
Use `.github/ISSUE_TEMPLATE/work-item.md` for further tasks and the PR template
for the ownership/review checklist.
