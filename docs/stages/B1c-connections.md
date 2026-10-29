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

## Development setup handoff — live acceptance still pending

Murtazo confirmed the Clerk/Meta test setup is not ready or known. PR #20's
foundation and web checks both succeeded at 81b73a7. A later browser attempt opened
the built public overview, but the browser connection became unavailable before
Connections/viewport checks could finish. The final visual acceptance remains open.

Akbar supplies or confirms access to the existing development resources; Murtazo
configures the integration and runs acceptance after those resources are ready.
Use local/hosting secret controls for actual values. GitHub records names and
redacted results only.

| Resource | Required configuration | Location |
|---|---|---|
| Existing Clerk development instance | NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY, CLERK_SECRET_KEY, existing redirect paths from web/.env.example | ignored web/.env.local |
| Same Clerk instance verification | AGENT_CLERK_ISSUER, AGENT_CLERK_JWT_KEY, AGENT_AUTHORIZED_PARTIES | ignored root .env |
| Isolated agent development database | AGENT_DATABASE_URL; review target before applying app.migrate | ignored root .env |
| Local backend destination | AGENT_API_URL=http://127.0.0.1:8000 | ignored web/.env.local |
| WhatsApp linking/webhook | AGENT_WHATSAPP_APP_SECRET, AGENT_WHATSAPP_VERIFY_TOKEN, AGENT_WHATSAPP_PHONE_NUMBER_ID, AGENT_WHATSAPP_BUSINESS_ACCOUNT_ID | ignored root .env |
| Public WhatsApp destination | AGENT_WHATSAPP_BUSINESS_NUMBER, international digits without plus | ignored root .env |
| Authorized outbound development sends | AGENT_WHATSAPP_ACCESS_TOKEN, AGENT_WHATSAPP_API_VERSION (explicit supported vN.0) | ignored root .env |
| Model-powered test result | AGENT_META_API_KEY, AGENT_META_MODEL (available development model) | ignored root .env |

Next runs locally at http://127.0.0.1:3000. Include that exact origin in the
backend's AGENT_AUTHORIZED_PARTIES JSON array when using it; localhost and
127.0.0.1 are different origins. The existing development Clerk instance must
support the same frontend. Rebuild the website after changing build-time public
configuration. Backend environment files load only when explicitly passed with
uv run --env-file .env, as in the root README.

Do authentication first: configure the matching Clerk instance and isolated agent
database, review/apply migrations to that development target, then run the API and
website. Test sign-in, provisioning, logout/re-login and isolation before starting
either worker. This stage does not need paid model calls to verify sign-in/status.

WhatsApp needs an approved HTTPS development webhook endpoint at
/webhooks/whatsapp, message-event subscription, the corresponding Meta test number
and consenting development recipients. Endpoint exposure/setup is a separate
explicit action. Confirm a numerical model-call/message budget and test recipients
before starting the model or delivery worker. app.whatsapp_worker --once can send
a real message; it is not a dry run. Never use production resources for fixture
tests or enable AGENT_TEST_ALLOW_RESET on a development database containing work
that should be retained.

### Live acceptance sequence

1. Sign in as test student A. Confirm bootstrap restores one agent across reload
   and logout/re-login. Record a redacted outcome, never a session token.
2. Use a separate browser session for test student B. Confirm distinct agents,
   private messages/results and separate connection/preferences state.
3. As A, create a verification message; confirm masking, explicit reveal/copy and
   expiry. Send it manually from A's consenting WhatsApp to the test destination.
   Check the server-confirmed last four digits. Repeat with B's own test number.
4. Save explicit consent, timezone and quiet hours. Refresh/re-login and verify
   persistence without changing the other account. Exercise unsaved edits and a
   recoverable API outage; edits should remain while saves are disabled.
5. After budget approval, send one synthetic academic request from A's linked
   WhatsApp. Observe durable task/result, provider acceptance and authenticated
   delivery evidence separately. B must not see A's result or receive its reply.
6. Check pause/unlink before a queued dispatch; verify saved work remains and an
   old-link task cannot be delivered to a new link. Do not promise recall of a
   request already authorized/dispatched. Unknown sends are not retried blindly.
7. Finish desktop, 390px and 320px browser checks with actual authenticated states,
   keyboard focus and navigation. Keep screenshots free of codes/private content.

Record date, tested revision, provider mode, consenting account aliases, observed
outcomes and failures in this work order/PR. Leave unchecked any unrun step.

## M1 integration review correction

Akbar's latest #4 instruction freezes feature expansion and requests independent
review of candidate #25 at a78b15a. Reviewed merge composition, unchanged Murtazo
API/transport/UI implementation, migration 001–007 inclusion and text-only worker
compatibility with the template contract. A4 remains excluded. Independently ran
247 backend and 44 web tests, Ruff lint/format, TypeScript and production build.
The ordinary web format check reported only Windows CRLF in README.md; checking
that file with end-of-line auto passed. No candidate code was edited.

Found and reported a blocking integration mismatch: the actual link endpoint
returns message/expires_in_seconds, whereas the controller and its mock expected
expires_at. Corrected the Murtazo controller on our branch, leaving the shared API
contract unchanged. Expiry starts before the request so network latency cannot
extend the displayed lifetime. Invalid or already-elapsed lifetimes remain
uncertain without automatic retry. Added an actual API contract assertion and
corrected/extended controller regressions. This is an M1 bug fix, not template
capability wiring or new feature scope. Live M1 remains pending setup and budget.

## Independent offline M1 scenario

While account setup is pending, added two verification-only cross-layer cases in
tests/test_whatsapp_flow.py. They bootstrap two synthetic accounts through the
authenticated API, obtain actual link challenges, sign inbound linking/messages,
save explicit preferences and run the existing reasoning worker against a
scripted tool-call/answer model. The existing delivery worker uses an injected
HTTP transport; all persistence uses disposable local Postgres.

The accepted path checks the exact recipient/reply, signed delivered callback,
replay and late sent callback without regression. The lost-response path remains
unknown and a fresh worker does not resend. Both check duplicate inbound IDs,
another account's private sentinel staying outside model context, link codes
staying outside model context, cross-account task denial, saved result privacy and
restored agent identity with a new API/Store instance. These are offline integration
regressions, not proof of real Clerk login, Meta inference or WhatsApp receipt.
No application behavior, shared contract or feature scope changed.

Validation on this onboarding branch: 193 backend tests pass after resetting the
verified disposable test schema to the branch's migration set; Ruff lint/format
and diff checks pass. The schema reset removed leftover 006–007 test migrations
from the earlier detached integration review, not a production/development store.

## Remaining offline control and public layout checks

Added three HTTP-to-worker regression cases for the existing controls. Pausing
before reasoning prevents a model call, retains the ready task and allows resume
to finish the same work. Pausing after a result is saved holds delivery with
reason paused and makes no transport call. Unlinking cancels the queued send,
clears the visible phone mapping and makes no transport call. A new API/Store
instance still reads the saved result in each case. Providers are synthetic.

Browser accessibility controls are available again. Inspected the built public
Connections view at 1440x900, 390x844 and 320x844, including the course panel and
footer by scrolling. Navigation labels fit at 320px, text wraps and panels remain
legible without visible horizontal clipping. This supersedes the earlier failed
public desktop/mobile recheck; no UI/CSS changes were needed. The authenticated
controls still require real Clerk setup, so their browser acceptance remains open.

Validation: all 196 backend tests pass on this branch, with Ruff lint/format and
diff checks passing. No application/shared/frontend implementation changed in this
verification checkpoint; the existing two dependency/synthetic-key warnings remain.

## Malformed webhook batch recovery

Error-path review reproduced five text-parser failures for malformed entries and
message collections. Because text extraction runs before status extraction, such
a sibling could cause the API to reject a signed batch containing valid delivery
evidence. The integration parser now filters object rows within arrays and checks
change/value/metadata/text shapes, preserving valid members and existing exact
business/number filtering. Raw-body signature verification still precedes parsing;
body bounds, storage failures and callback correlation are unchanged.

New regressions cover a valid text among malformed siblings, four invalid message
collection shapes, and a signed valid status alongside malformed text with replay.
Five unit cases failed before the fix. The focused transport/API suites pass all
82 cases. Independent scoped review found no actionable regression. No new
messaging capability, shared schema or live provider access was introduced.

Full validation: 202 backend tests pass on the onboarding branch, with Ruff lint,
format and diff checks passing. Two existing dependency/synthetic-key warnings
remain. Integration candidate validation must follow incorporation by its owner.

## Live test preparation

[M1 live test pack](M1-LIVE-TEST-PACK.md) provides two synthetic student scenarios,
exact harmless messages, observable core/control pass criteria, a bounded usage
proposal requiring explicit approval and a blank redacted execution record. It
supports the integration candidate's docs/M1-ACCEPTANCE.md. Every live case is
Not run; preparing the sheet does not configure accounts or authorize provider use.
