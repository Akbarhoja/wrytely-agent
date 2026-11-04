# Wrytely engineering agreement


## November 3 supervisor delivery amendment

Follow [one-course delivery and exact parallel assignments](docs/ONE-COURSE-DELIVERY.md).
This supersedes stop-before-P2 and the sequential stage-completion freeze.
A retains remaining P1 and runtime/shared/contracts; M starts app/WhatsApp/web/deploy
assembly for the one-course autonomous journey. No duplicate collector/runtime.
Original full-product P0–P6 gates remain unpassed until their evidence exists.

## Authority and scope

Akbar is supervisor/product owner. Codex is lead engineer. Murtazo is engineer for
integrations and the web experience. Read TEAM.md, STATUS.md, CONTRACTS.md and your
current work order in docs/WORK-ORDERS.md before editing. docs/BUILD-PLAN.md revision7
is the active scope: own Meta-powered runtime, Canvas extension, Outlook email and
WhatsApp. Old stage documents are historical context, not competing instructions.
Codex owns runtime/shared/contracts; Murtazo owns extension/integrations/app/web/deploy.
Do not silently narrow required behavior to meet a deadline or provider blocker.

Current supervisor exception: Akbar/Codex owns **all remaining P1 completion**,
including the extension, provider/HTTP assembly and web work normally owned by M.
See TEAM.md's current P1 ownership. M pauses overlapping P1 implementation and
hands off unpublished work; reuse his delivered code. Optional Outlook stays paused,
P0 WhatsApp stays M-owned, and P2–P6 default ownership is unchanged. This explicit
reassignment removes the cross-surface edit restriction for P1 only.

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
- One coherent PR per complete feature or substantial fix. Use `codex/` for Codex branches.
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

## Streamlined execution — supervisor decision November 1

Akbar explicitly removed routine agreement gates and excessive coordination overhead.
This section supersedes older mandatory claim/consumer-agreement wording in plans,
proposals and historical issue comments, including the pending #157 design gate.

Keep one owner per implementation area and check active work before editing. Record
one concise owner/branch/feature entry at the start of a substantial feature; an
acknowledgment, issue number or exact-file claim is not permission to begin owned work.
Do not duplicate active work, silently take another engineer's files or push their branch.
Only Akbar reassigns ownership; his current instruction does not reassign M's journal.

The interface owner may decide, document and implement a versioned boundary in their
scope immediately. Notify the consumer asynchronously with concrete signatures,
examples and tests; do not wait for a ceremonial agreement. Pause only the affected
work for a concrete incompatibility, conflicting active edits or an actual required
external decision. A owns Store/contracts/runtime; M owns HTTP/extension/UI assembly.
Existing code must be reused; no parallel store, journal or runtime.

Batch related changes into complete, reviewable features. Do not create a separate
proposal/PR/handoff for each utility or routine substep. Use focused checks while
building and combined regression checks before feature review/integration. Preserve
required independent human approval, CI and protected-branch rules for merging.
Update STATUS and #4 at meaningful handoffs, blockers or feature completion; no
repeated approval prompts or unchanged-status comments. Mark capability complete
only with its actual acceptance evidence.

## Current execution order

Follow P0–P6 in docs/WORK-ORDERS.md. Read the code audit before replacing existing
modules. Interface owners publish versioned decisions and proceed; planned names are not
implemented methods until code exists. Tests belong to the implementation owner. Preserve historical
evidence, active budget limits and current blockers when shortening status notes.
Documentation-only changes require formatting/link/diff checks; unchanged application
code does not need a redundant local executable suite. CI evidence remains separate.
