# M private preparation consumer

Claim: [coordination #4](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6644234620).
Branch `codex/course-preparation-view`, based on A preparation head
`ce7e6f84824b33a7f183c35d2c92c5686924f753` (PR170). This is a consumer
of [preparation v1](contracts/COURSE-PREPARATION-v1.md), not a second runtime.

## Behavior

The existing private course-supervision panel displays the additive `preparations`
projection returned by the existing verified-session HTTP routes. Each checklist
shows the server notice, literal original quotations, clarification questions,
source coverage, missing reasons and unread-continuation warning. `current` means
limited source pins remain inspectable; it never means complete or approved work.
Historical records remain visibly historical. Checklists have no draft acceptance,
download or send actions; existing ordinary offer controls retain their own gates.

The consumer rejects malformed, unbound, duplicate or oversized preparation data.
Older servers omitting the additive field remain compatible. A refresh clears the
previous preparation projection before fetching; failed or malformed responses do
not leave stale checklists claiming current evidence. Access, account and session
changes clear private state through the existing keyed/aborted session boundary.
No preparation content is added to browser storage.

## Verification at this checkpoint

- 21 focused UI tests passed; full web suite: 165 passed. TypeScript passed.
- 27 preparation/API checks passed against disposable Postgres with migration029.
  The two new HTTP tests use the real Store and existing session verifier fixture:
  owner isolation, no-store responses, forged-owner rejection, pause/history,
  unchanged call count and no responsibility/artifact/outbound creation.
- Ruff lint and 310-file format check passed; changed-file Prettier/diff checks.
- Real component with synthetic data inspected in IAB at 390, 768 and 1440px.
  Existing sage/Plus Jakarta styling retained; spacing adjusted after mobile review.
  Chrome and the user's original preview were untouched.
- Production webpack build passed. Complete backend regression is running in its
  separate disposable database; no full-suite pass is claimed before its result.

The separate older M backend suite uses its original worktree/database and is not
coverage of migration029 or these new API tests. This branch does not duplicate
PR166's pending worker-origin/API-client fixes; A must integrate those separately.
A's full PR170 CI, migration activation and counterpart review remain gates.
No migration deployment, model invocation, source collection, native real-course
file, WhatsApp transmission or phone receipt is demonstrated by this change.
