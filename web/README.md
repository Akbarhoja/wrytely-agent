# Wrytely student workspace

Next.js App Router, React, Clerk Core 3 and the existing Python agent API. This is
new code; it does not import the existing Wrytely application's source or secrets.

## Start

Node 24 and npm are used in CI.

```sh
npm ci
npm run dev
```

The public workspace shell renders without credentials. It shows connections as
coming soon and disables agent actions. It creates no dummy accounts or tasks.

For actual development sign-in, configure the **existing Wrytely Clerk development
instance** in ignored `web/.env.local` using `web/.env.example` as the variable
reference. Do not run `clerk init`, create a replacement app, use production keys,
or paste secrets into a PR. Provide values at build time and runtime; rebuild after
changing the publishable key. The Python backend must verify the same instance's
issuer/public key and permit the exact frontend origin in authorized parties.

Run the migrated Python backend and worker separately, following the root README.
`AGENT_API_URL` is server-only and points at that backend. No Meta key or database
credential belongs in the web app.

## Request path

Browser → same-origin `/api/agent/*` → verified Clerk session → Python `/v1/*`.
The web server obtains the session token and forwards it as a Bearer token. The
backend independently verifies ownership. Caller-supplied identity and auth headers
are not forwarded. POSTs require an exact matching Origin; routes are allowlisted,
redirects disabled and private responses are not cached. Proxy exception bodies
are never returned to the browser.

Only public shell routes work without Clerk configuration; private API calls fail
closed. No test-session switch or authentication bypass exists in the runtime.

## Conversation behavior

- Bootstrap restores the same account's agent.
- Message submission creates a durable task, then the UI watches its state.
- A lost response retains the original content and idempotency key; retry sends
  that same request even after a reload. It cannot silently create duplicate work.
- Unsent text, unresolved submission and current task ID are saved in tab-scoped
  sessionStorage under a user-specific key. They are never placed in URLs. No
  credentials are stored there. Closing the tab clears this browser storage;
  disabling storage leaves in-memory recovery only. This is not cross-device draft
  synchronization. The component remounts when the Clerk user ID changes.
- Pause/resume is confirmed with the API. Paused work remains saved; polling stops
  until resumed. A failed poll stops with a reconnect action rather than claiming
  completion.
- Canvas, Teams, calendar and outbound messaging are not implemented here.

## Design

The workspace uses a restrained green palette, self-hosted Plus Jakarta Sans,
Phosphor icons, a work-first overview and a separate conversation view. The default
screen groups real saved tasks into In motion, Needs attention and Completed.
Decision requests have their own future integration area; blocked execution is
not presented as a request for approval. Empty
states explain what can happen next without inventing assignments or activity.
`GET /v1/tasks` provides only the authenticated account's most recent 50 tasks.
The overview refreshes saved work independently of the conversation; it stops
refreshing while paused, on unmount or after a read failure. A reconnect action
restores reads. Unknown/unloaded work is distinguished from a verified empty list.

All interactive elements have visible focus, labeled controls and reduced-motion
support. Phone layouts stack the workspace and activity panel.

## Checks

```sh
npm run format:check
npm run typecheck
npm test
npm run build
```

Tests cover the server forwarding boundary and student interaction/recovery with
simulated sessions and responses. Browser checks cover the unconfigured shell and
connection view at desktop and phone sizes. They do **not** verify live Clerk
signup or Meta inference.

Before marking M1 complete, use two actual development accounts to verify distinct
agents, private results, session expiry, refresh/re-login, retry recovery, pause,
and an actual message → Python queue → Meta worker → saved response round trip.
No public deployment or pilot is enabled by this scaffold.

## WhatsApp connection controls (issue #17)

The Connections view reads authenticated GET /v1/whatsapp after agent provisioning.
The verified session determines ownership. The response contains linked status,
last four digits, nullable saved preferences and historical delivery status.
Link generation is unavailable until the backend has webhook configuration and
AGENT_WHATSAPP_BUSINESS_NUMBER (public international digits, distinct from Meta's
internal number ID). Configuration does not prove a live connection.

`whatsapp-connection.tsx` contains the testable view and preference form. Codes are
masked, expire from display, and are never put in URLs or browser storage; the
controller clears its in-memory challenge on expiry/account/session change.
Link/unlink callbacks have a submission lock. Unlink asks for a separate inline
confirmation and restores keyboard focus. Preference saves are explicit and new
authoritative reads reconcile without silently discarding edited drafts. Recoverable
read failures retain unsaved preference drafts with saves disabled. Interrupted
mutations are not replayed; a fresh status check is required before another action.

The existing proxy allowlists GET whatsapp and POST whatsapp/link, whatsapp/unlink and
whatsapp/preferences in addition to previous routes, preserving exact Origin,
verified session and no-cache rules.
Current web validation: 56 tests, format check, typecheck and production build
pass. Ready/linked/error states use simulated API responses in tests; live two-account
Clerk, actual linking and provider delivery remain unverified. See
`docs/stages/B1c-connections.md` and root DESIGN.md for scope and design decisions.

For the ordered Clerk/Meta development setup and two-account live checklist, see
[the setup handoff](../docs/stages/B1c-connections.md#development-setup-handoff--live-acceptance-still-pending).
The local dev server uses http://127.0.0.1:3000; backend authorized parties must
include the exact origin used by the browser. Authentication/status checks can run
before enabling either model or WhatsApp delivery workers.

## Configured loopback requests

Keep `skipProxyUrlNormalize: true` in next.config.ts. Next otherwise changes
127.0.0.1 to localhost in the middleware request URL. Clerk's same-page rewrite
can then be treated as an external proxy back to this server, repeatedly entering
middleware instead of reaching the page/API handler. Preserving the original URL
keeps that rewrite internal; it does not disable Clerk or backend authentication.

The real-SDK origin regressions use synthetic test-format keys with provider
fetches blocked. Offline production HTTP checks cover fast root/sign-in responses,
the signed-out browser redirect and private 401; they do not prove real login.

## Academic context snapshots

The existing authenticated proxy now allows GET sources, GET sources/{uuid} and
POST sources. Creation accepts {title, content} with a UUID Idempotency-Key; reuse
the same key and exact payload after a lost response. Changed text needs a new key.
The backend records manual snapshot coverage and server retrieval time. Saving
does not start reasoning, draft an assignment or send a message. Lists contain
the latest 50 source summaries, with private detail available by source ID.

The Academic context workspace view lets a signed-in student paste, save and open
snapshots. Unsaved text survives switching workspace tabs but is kept in memory
only; refreshing/closing clears it. Account/session changes clear private state.
An uncertain save keeps its exact key/payload for explicit retry; source content
is displayed as plain text. Lists are bounded to 50 current sources.

All 68 web tests, TypeScript, formatting and production build pass. Offline browser
checks cover desktop and phone layout and lost-response/keyboard recovery using
fictional fixtures. Real authenticated backend intake still needs operator testing.
Explicit delegation remains subsequent B2 work; see
[the B2 work order](../docs/stages/B2-context-intake.md). No live B2 result is claimed.

## Private results

The Private results view lists the account's latest 50 responsibilities and up to
50 saved drafts per selected responsibility. Its read-only proxy paths are GET
responsibilities, GET responsibilities/{uuid}/artifacts and GET artifacts/{uuid}.
The API reuses existing Store projections; no readiness mutation or public link
is exposed. Storage failures stay errors and responses use no-store.

Students can read the draft, disclosure, citation evidence and stored checks.
Current ready state plus a passed report is required for Ready for your review.
Changed sources override historical success; failed/missing checks stay visible.
Model assessments remain fallible. Viewing does not send, share or submit work.
New selections, identity changes and session expiry cannot display a late result
from another request/account. This is offline-verified presentation of existing
artifacts; real authenticated operator acceptance remains pending.

## Private-draft API preparation

POST responsibilities now accepts only objective, 1–8 distinct source_ids and
confirm_private_draft=true, with a UUID Idempotency-Key. It calls the reviewed
atomic Store boundary under the verified session. Replay preserves the original
private intent; changed input or an analysis-only key conflicts. The server fixes
the step/revision budgets at 6/2 and uses its configured pending-task limit.
No browser policy, owner, readiness or budget fields are accepted. A receipt
contains only responsibility_id and requested_mode=private_draft.

GET responsibilities/{uuid}/status exposes the published controlled private status
projection. Missing and other-account work share the same 404. Reads and writes
use no-store; the existing proxy requires verified auth and same-origin mutation.
Academic context now mounts the private-draft consent form using its existing
loaded snapshots. Confirming sends only the objective, selected source IDs and
explicit private-only intent. An uncertain save keeps its exact key/payload for
manual retry. Definite rejection clears consent for review; a saved receipt shows
the controlled status and a path to Private results. Status refreshes are GET-only
and never start or retry work. Selected responsibilities also show that status in
Private results. Account changes and session expiry clear private views, including
hidden context inputs; delayed responses are ignored.
No retained development database was migrated or worker enabled by this change.
Live model usage still requires its separate explicit development budget.
