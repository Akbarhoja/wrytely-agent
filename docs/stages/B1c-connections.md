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
- [ ] Agree status contract and public destination configuration in #4.
- [ ] Implement status/read assembly and tests using the owner's Store method.
- [ ] Add connection/preference UI with uncertainty, expiry and account isolation.
- [ ] Verify actual rendered UI, component tests, build and affected backend suite.
- [ ] Independent review, draft PR, and exact offline/live limits in #17.

## Prepared UI checkpoint — October 28

The existing Connections view now includes an honest WhatsApp setup panel and
removes fabricated zero connection counts. A separate view component prepares
verified/disconnected, masked expiring challenge, explicit preferences, confirmation,
loading/error/session and uncertain-action presentations. Link/unlink actions are
submission-locked. Confirmation focus is moved/restored after rendering. Saved
preference updates refresh clean forms; dirty drafts are retained with an explicit
choice to use saved preferences.

Important: the actual signed-in workspace currently mounts the unavailable state.
The controller/status API assembly is NOT implemented. Ready-state tests use
controlled component props, not a live Clerk session or a fake runtime account.
The requested Store read and public destination configuration remain unagreed in
#4; dependent wiring is intentionally blocked. No new GET route is allowlisted.

Validation: 35 website tests pass, including seven panel interaction tests and
17 proxy-boundary tests. TypeScript, Prettier and production build pass. Strict
static UI audit reports no findings. DESIGN.md lint reports zero errors and six
unused-document-token warnings (runtime CSS remains canonical). Impeccable reports
one taste warning for the incumbent Plus Jakarta Sans font; it is deliberately
preserved for this scoped extension, not silently replaced as a rebrand.
Browser inspection covers the actual unavailable view at desktop and phone widths;
ready-state interaction evidence is component-test-only. Independent review found
three issues, each reproduced by a regression and fixed; re-review found no blocker
for this scoped preview. No backend files, migrations, live provider calls or
production configuration changed.
