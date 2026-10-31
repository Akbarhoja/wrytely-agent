# Canvas pairing HTTP assembly plan

Execute directly under P1-M1's separately reviewable lifecycle assembly slice;
claim [#63](https://github.com/Akbarhoja/wrytely-agent/issues/63).

**Base:** Reviewed #62 `682ce16`, including accepted #59 lifecycle implementation.
**Goal:** Connect existing Clerk verification and operator Settings to accepted Store
pairing/read/revoke/bind methods without introducing sync or provider access.
**Architecture:** Scoped APIRouter with bounded JSON requests and no-store/redacted
errors; mount from existing create_app and reuse its identity/database dependencies.
**Files:** app/source_connections.py, app/main.py assembly only, dedicated API tests,
this plan and a scoped handoff. Shared Settings/Store/schema remain Akbar-owned.

- [x] Review #62 delta; run 38 independent config/delivery cases and record acceptance.
- [x] Claim exact files/branch and coordinate before edits.
- [x] Write failing HTTP tests using real disposable Store and test-only session verifier.
- [x] Add private pairing issuance/read/revoke and code redemption/credential bind.
- [x] Forward settings.canvas_origins to the single existing Store constructor.
- [x] Enforce strict bodies, 16 KiB stream limit, JSON content type, role separation,
      generic secret-free errors and no-store, with default-disabled credential operations.
- [x] Verify two-account isolation, replay/rates/expiry, changed-subject revocation,
      storage failure and absence of source/model/outbound work.
- [x] Run focused tests, required full backend/Ruff/format, independent review and draft PR.

No actual origin/env values, provider grant, public rollout, migration execution on a
retained database or deployment. Future public HTTP rate limiting/operational readiness
is separate from Store's schema-valid redemption budget. Scope/sync/Outlook methods
are not assumed implemented. P0-M1 live session checks remain open.

Evidence: baseline HTTP tests16 failed; final API21 passed, including2 direct ASGI
stream-boundary cases. Full backend503 passed before adding the2 route-only cases;
application code unchanged after that run. Ruff check/format and diff checks pass.
Read-only reviewer found no blocker; requested raw ASGI coverage added and passed.
Draft PR publication and counterpart review are the handoff, not a merge or release.
