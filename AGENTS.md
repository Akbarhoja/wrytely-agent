# Wrytely engineering agreement

## Authority and scope

Akbar is supervisor/product owner. Codex is lead engineer. Murtazo is engineer for
integrations and the web experience. Read TEAM.md, STATUS.md, CONTRACTS.md and your
current work order in docs/WORK-ORDERS.md before editing. docs/BUILD-PLAN.md revision7
is the active scope: own Meta-powered runtime, Canvas extension, Outlook email and
WhatsApp. Old stage documents are historical context, not competing instructions.
Codex owns runtime/shared/contracts; Murtazo owns extension/integrations/app/web/deploy.
Do not silently narrow required behavior to meet a deadline or provider blocker.

Reuse existing Wrytely services as agreed, but do not change the existing product
repository or production configuration as a side effect. Agent migrations stay
inside `wrytely_agent`. Use isolated Postgres for tests. No production migrations,
public signup, connector authorization, or deployment occurs merely because a
stage exists in a document.

## Collaboration

- Read relevant code and diffs freely. Coordinate edits across ownership areas.
- Runtime/shared/contracts: lead engineer owns design and integration review.
- Integrations/app/web/deploy: Murtazo owns the integration work orders.
- `app/` connects concrete implementations; runtime depends on contracts.
- One coherent PR per stage/fix. Use `codex/` for Codex branches.
- Review Murtazo's diff, tests, interface compliance and integrated behavior
  before merging. Report observations to Akbar without claiming unseen work passed.
- Murtazo is murtazokhon-tech. Project communication in GitHub issues/PRs is
  authorized by Akbar; do not expand that authorization to unrelated channels.

## Correctness

- Ownership comes from verified sessions, never browser-provided user IDs.
- No auth bypass flags, fake production tokens, unscoped retrieval or public files.
- No secret values in source, logs, PR bodies or chat. Inspect configuration names,
  not existing environment-file contents.
- Persist first; notifications are hints. Respect leases and attempt fencing.
- Never blindly retry a potentially delivered external send. Represent unknown
  outcomes honestly. Implemented transport is not evidence of live delivery.
- Model/source content cannot override authorization. Check control changes before
  tools and result delivery.
- Check STATUS.md for actual capability. Draft checks exist, but semester supervision,
  automatic Canvas/Outlook collection and live continuous operation are unfinished.
  Never describe the bounded reply loop as the completed academic agent.

## Validation and reporting

Run focused tests while editing; run `uv run ruff check .`,
`uv run ruff format --check .`, and `uv run pytest -q` before review. Tests use
local disposable Postgres or explicitly designated test databases, never production.
Live provider calls require a configured development key and explicit test budget.
Continue until all work-order checks pass or record the precise remaining blocker.
Update STATUS.md with actual evidence and limits. Do not commit `.env` or `.venv`.

## Mandatory ownership and coordination gate

Before implementation, read TEAM.md and the pinned coordination issue linked
there. Claim one work item with owner, branch, files and acceptance checks. Check
other active claims. Codex may implement runtime/shared/contracts and their tests;
Murtazo implements messaging/sources/app/web/deploy and their tests. Existing
scaffolds must be reused. Never duplicate another owner's module or take over
because they are absent, blocked or slow. Only Akbar may explicitly reassign work;
record his authorization in the issue before crossing scope.

If a dependency or shared file is needed, post the precise requested interface or
change in the coordination issue and wait for agreement from its owner. Continue
unblocked work inside your own scope. A file claim with another owner blocks edits
until they release it or Akbar reassigns it. Do not push into another's branch.
Every implementation PR links its claimed issue and documents tests, interface
changes, limits and handoff. Review the other engineer's changes and integrate
through PRs. Mark done only after acceptance evidence and review. Existing draft
baseline PR #3 predates this claim gate; the gate applies to new implementation.

## Current execution order

Follow P0–P6 in docs/WORK-ORDERS.md. Read the code audit before replacing existing
modules. New shared interfaces require counterpart agreement; planned names are not
implemented methods. Tests belong to the implementation owner. Preserve historical
evidence, active budget limits and current blockers when shortening status notes.
Documentation-only changes require formatting/link/diff checks; unchanged application
code does not need a redundant local executable suite. CI evidence remains separate.
