# Wrytely engineering agreement

## Authority and scope

Akbar is supervisor/product owner. Codex is lead engineer. Murtazo is engineer for
integrations and the web experience. Read TEAM.md, STATUS.md, CONTRACTS.md and your
current work order before editing. The current work follows the active track: Codex runtime/memory/verification and
Murtazo messaging/onboarding/sources. Read docs/stages/B1-murtazo.md before integration work.

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
- Ask Akbar for Murtazo's GitHub identity before configuring user-specific review
  assignment. Do not message collaborators unless Akbar authorizes the message.

## Correctness

- Ownership comes from verified sessions, never browser-provided user IDs.
- No auth bypass flags, fake production tokens, unscoped retrieval or public files.
- No secret values in source, logs, PR bodies or chat. Inspect configuration names,
  not existing environment-file contents.
- Persist first; notifications are hints. Respect leases and attempt fencing.
- Never blindly retry a potentially delivered external send. Represent unknown
  outcomes honestly. Initial foundation has no external send capability.
- Model/source content cannot override authorization. Check control changes before
  tools and result delivery.
- Full academic planning, connectors and artifact checks are future stages. Do
  not describe the current bounded reply loop as the completed academic agent.

## Validation and reporting

Run focused tests while editing; run `uv run ruff check .`,
`uv run ruff format --check .`, and `uv run pytest -q` before review. Tests use
local disposable Postgres or explicitly designated test databases, never production.
Live provider calls require a configured development key and explicit test budget.
Continue until all work-order checks pass or record the precise remaining blocker.
Update STATUS.md with actual evidence and limits. Do not commit `.env` or `.venv`.
