# Student WhatsApp controls

Owner: Murtazo. Work item #17. Branch `murtazo/onboarding-connections`, stacked
on #14. Reuse existing Next.js/Clerk workspace, same-origin proxy and Store.

## Intended behavior and visual direction

Extend the existing Connections view with WhatsApp linking and communication
preferences. Preserve the work overview as the default view and the existing
green/Jakarta identity. Use one main connection section, with separate timing
controls below; avoid promotional copy or artificial activity. The distinguishing
detail is an explicit, readable verification sequence: request a code, send it
from your own WhatsApp, then check the server-confirmed connection.

Keep codes in memory only. Expiry clears the code; account change/remount clears
all private state. Neither a number entered by the student nor a successful code
request establishes ownership. Unknown reads remain unknown. Mutations use
explicit confirmation/reconciliation, not automatic retries after lost responses.

Unlink uses an inline confirmation naming the consequence: queued WhatsApp replies
are cancelled; an already dispatched request cannot be recalled. Preference saves
are explicit; timezone/quiet hours and consent are separate from link ownership.

## Boundaries

Existing POSTs: whatsapp/link, whatsapp/unlink, whatsapp/preferences. Allowlist them
through the existing exact-Origin proxy. Shared GET status and destination-number
configuration are requested in #4; dependent assembly waits for owner's agreement.
No shared code, new database client, replacement auth, live sends or deployment.

## Verification

Proxy route/auth/Origin tests; component interaction/recovery tests; backend
two-account status tests after shared read is available. Run website format,
typecheck, tests and build; backend checks for API edits. Inspect real browser
at desktop and phone widths; do not represent simulated sessions as live Clerk.

## Plan

- [x] Allowlist existing mutations with boundary tests (independent of status read).
- [x] Agree status contract and public destination configuration in #4; integrate #19.
- [x] Implement status/read assembly and tests using the owner's Store method.
- [x] Add connection/preference UI with uncertainty, expiry and account isolation.
- [ ] Finish authenticated browser/live checks; offline tests and build are verified.
- [x] Independent review, draft PR #20, and exact offline/live limits in #17.

## Prepared UI checkpoint — October 28

The existing Connections view now includes an honest WhatsApp setup panel and
removes fabricated zero connection counts. A separate view component prepares
verified/disconnected, masked expiring challenge, explicit preferences, confirmation,
loading/error/session and uncertain-action presentations. Link/unlink actions are
submission-locked. Confirmation focus is moved/restored after rendering. Saved
preference updates refresh clean forms; dirty drafts are retained with an explicit
choice to use saved preferences.

The shared read/configuration boundary was agreed in #4 and supplied in #19.
After reviewing the diff, integrated it into this branch without editing shared
owner files. Authenticated GET /v1/whatsapp uses the verified user ID and returns
only the agreed private snapshot plus public destination/configuration readiness.
Storage failure remains 503, not disconnected. GET success and the proxy use
no-store. API tests cover two synthetic accounts, ignored query identity, saved
preferences, session restoration, unlink, readiness and storage failure.

The actual signed-in workspace now uses the account-scoped controller after
provisioning. Aborted/obsolete-account responses cannot update visible state.
Challenges remain in memory, expire and clear on session/account loss. Mutations
are locked, never automatically retried, and uncertain outcomes require a fresh
status read. Unlink/preferences require confirming reads. Recoverable refresh
failures preserve dirty preference drafts with actions disabled; permission errors
show a recovery action. Account delivery is explicitly historical, including the
distinction between provider acceptance, pending, unknown and recipient delivery.

Validation: 44 website tests pass, including 15 panel/controller tests and
18 proxy-boundary tests. All 190 backend tests pass on disposable local Postgres;
Ruff lint and format pass (two existing test-library/synthetic-key warnings).
TypeScript, Prettier and production build pass. Strict
static UI audit reports no findings. DESIGN.md lint reports zero errors and six
unused-document-token warnings (runtime CSS remains canonical). Impeccable reports
one taste warning for the incumbent Plus Jakarta Sans font; it is deliberately
preserved for this scoped extension, not silently replaced as a rebrand.
Browser inspection covered the earlier actual unavailable view at desktop and phone
widths. The final production browser recheck failed at the browser connection layer
although terminal HTTP returned 200; no authenticated browser or final 320px check
is claimed. Ready-state interaction evidence is automated-test-only. Independent
review findings were reproduced and fixed with regressions, including preserving
drafts on refresh failure and recovery after rejected mutations. Own backend change
is API assembly only. No migrations, live provider calls or production configuration
changed. Actual Clerk two-account, webhook linking and delivery checks remain open;
template policy remains Codex-owned and expired-window sends remain held.
