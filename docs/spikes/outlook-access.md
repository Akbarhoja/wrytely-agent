# Outlook access feasibility — P0-M2

Owner Murtazo/local assistant. Claim [#53](https://github.com/Akbarhoja/wrytely-agent/issues/53).
Branch `codex/outlook-access-feasibility`, base `9bbea97`. Canvas #51/#52 stays saved;
its live session evidence waits for the user's exact origin/course/install scope.

## Current result and scope

Implemented an offline-tested Microsoft Graph read probe, not an authorized Outlook
connection. No school mailbox, Microsoft app registration, OAuth grant, token refresh,
notification subscription, attachment download or server ingestion was performed.
No mailbox content or credentials are stored by this helper. P0-M2 remains incomplete.

`integrations/outlook/read_probe.py` reuses existing httpx/Pydantic dependencies.
`probe_inbox(client, token: SecretStr, expected_subject=..., cursor=None, max_pages=3)`
accepts trusted operator inputs only. Expected subject must come from a verified OAuth
provider flow, bound to the signed-in Wrytely account; a browser-posted identity is
not sufficient. The helper cannot establish application ownership or grant consent.

It checks `/me`, resolves the actual Inbox folder ID, reads its delta pages and checks
`/me` again. The returned `summary` has counts and round state only. Private `next_link`
and `delta_link` fields are excluded from repr; **serialize/log only summary**, never
the whole result, HTTP requests, cursors or provider error bodies. Tokens are ephemeral
caller inputs, never loaded from an environment file or acquired by this helper.

Global Graph host only, HTTPS, GET-only and redirects disabled even if a caller's client
defaults to following them. Continuation URLs must stay on the same resolved folder
delta endpoint with allowed query keys. The provider's opaque URL is preserved exactly.
Unexpected URL forms are blocked until reviewed; national-cloud hosts and alternate
OData folder-path syntax are not implemented. This is not a general URL fetcher.

Bounds: 1 MiB decoded response, 1,000 change records per call, default 3/max 10 pages,
15 seconds per request. Configure the eventual caller with zero transport retries,
no HTTP request hooks/logging (including httpx INFO request lines), and no credential-bearing
proxy. Ordinary HTTP INFO logs can expose cursor URLs, so the live operator must disable
httpx/httpcore request logging rather than merely omit debug mode. The helper performs no
automatic retry.
A partial round returns a validated next checkpoint; failed rounds return no checkpoint.
401/403/410/429/outage remain controlled reconnect/access/reset/rate/outage failures.
Retry-After seconds are reported only within 0–3,600; longer/unknown/date forms remain
unknown rather than inventing a shorter backoff.

The probe inspects body presence and change counts, then discards provider content.
Duplicate IDs count separately as change records and once in unique-ID counts; this is
not a production deduplication/event implementation. A folder removal can mean a move,
so it is labeled `removed_from_folder_records`, never confirmed mailbox deletion.
Body presence and a complete Inbox delta round do not prove whole-mailbox coverage,
attachment extraction, semantic academic matching or live update availability.

## Consent and account readiness

Before a real test, Akbar must confirm the existing Microsoft development app route,
school tenant/account and consenting mailbox. Request only readiness/configuration
names in GitHub; credentials belong in approved secret controls. Do not create a second
app, scrape Outlook UI, use password grant or request application-wide mail access to
work around institutional consent. Admin restrictions remain a real blocker.

For the required message bodies/attachments, propose delegated `Mail.Read`; basic-mail
permission omits those contents. `/me` identity checking needs the appropriate delegated
`User.Read`. Server continuation requires explicit `offline_access` and an authorization
code flow; use `openid` only with actual OIDC identity validation. Do not request
`Mail.Send`, `Mail.ReadWrite`, shared-mail or calendar permissions. Institutional consent
policy can still require admin approval even when a delegated scope allows user consent.
[Permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference),
[delegated authorization](https://learn.microsoft.com/en-us/graph/auth-v2-user).

Mail.Read authorizes a broader mailbox reading capability than the selected Inbox probe.
Explain that scope accurately; folder selection is an application collection boundary,
not a Graph permission that cryptographically confines the token to Inbox. Before pilot,
agree relevant folder selection, retention/deletion and unrelated-mail minimization.

## Future OAuth assembly — requires agreed C1 and storage

1. An authenticated Clerk session starts connection. Server generates an unpredictable,
   expiring one-use state and PKCE S256 verifier/challenge, bound to that session,
   requested tenant/scopes and exact registered callback. No secrets in browser storage.
2. Callback atomically consumes valid state, rejects replay/mismatch and exchanges code
   using the matching verifier/redirect. Validate issuer/audience/nonce for any ID token;
   obtain Graph identity with the returned authorized token. Confirm account mismatch
   explicitly rather than attaching a different mailbox silently.
3. Akbar-owned shared storage binds provider subject to the Wrytely owner, generation,
   scope and encrypted credential handle. M implements only provider/HTTP assembly.
   Never use an address typed into a request as authoritative identity.
4. Refresh remains server-side under the current generation and secret handle. Revoke
   disconnect/old generations, surface reconnect needs, and discard late commits. No
   file/environment plaintext token store or independent database client.

These are requirements for future assembly, not an implemented OAuth endpoint.

## Incremental reads and notifications

Message delta is per folder. Follow all `@odata.nextLink` pages, then retain the final
`@odata.deltaLink`; query options belong on the initial request rather than modifying
opaque continuation URLs. Store each selected folder's checkpoint atomically with
committed observations, coverage and check receipts. On invalid/expired delta state,
request a bounded rescan through the shared protocol; never silently erase evidence.
[Message delta](https://learn.microsoft.com/en-us/graph/api/message-delta).

Request immutable IDs consistently on reads and later subscription creation. They
survive moves within the same mailbox, with documented archive/export exceptions.
Retain connection/mailbox namespace; immutable message ID is not a global student ID.
[Immutable identifiers](https://learn.microsoft.com/en-us/graph/outlook-immutable-id).

Notifications are wake hints. Future webhook assembly must validate subscription,
tenant/clientState and current connection generation before durably queuing a catch-up.
The subscription-validation challenge is a POST with an opaque validationToken query;
return its decoded plain text within the documented validation window. For ordinary
events, acknowledge only after durable queueing, otherwise return failure. Never follow
an arbitrary notification resource URL or assume a notification contains full email.
[Webhook protocol](https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks).

Read actual expiration from each created subscription and renew before it expires.
Handle lifecycle/revocation and duplicate/lost events with delta catch-up; laptop-closed
coverage requires the authorized cloud connector and operational budget. Basic
notifications are the initial design; rich encrypted notifications add a separate
certificate/encryption protocol and are not implemented.
[Outlook notifications](https://learn.microsoft.com/en-us/graph/outlook-change-notifications-overview).

Actual attachment contents require separate authorized reads and bounded extraction,
not `hasAttachments` or a filename. Inline, item and reference attachments need separate
coverage/error behavior; never auto-fetch an arbitrary linked drive/website.
[Attachment reads](https://learn.microsoft.com/en-us/graph/api/message-list-attachments).

## Evidence matrix and handoff

| Gate                                 | Current evidence      | Remaining action                                 |
| ------------------------------------ | --------------------- | ------------------------------------------------ |
| GET-only identity/folder/delta flow  | Scripted tests        | Authorized school-account test                   |
| Cursor replay/limits/unsafe URLs     | Scripted tests        | Confirm actual provider link forms               |
| Expiry/403/410/429/timeout/redirect  | Scripted tests        | Real consent/revocation observations             |
| Consent and admin policy             | Not run               | Existing app/account readiness from Akbar        |
| Actual email bodies and attachments  | Not run               | Explicit mailbox scope and authorized reads      |
| Subscription validation/renewal      | Not implemented       | C1/C2 persistence and reviewed HTTP assembly     |
| Missed notifications / laptop closed | Not run               | Deployed bounded cloud connector test            |
| Cross-account connection isolation   | No app connection yet | Shared generation/owner tests plus assembled API |

Akbar's AI acknowledged our #48 feedback and published revision `855c46b` with exact
sync/replay/digest and byte-handoff proposals. Those remain separate owner review and
agreement; this probe consumes no proposed Store method. Provider checkpoints must
eventually be scoped to connection generation and folder in Akbar's shared storage.

STATUS.md remains held by Akbar's active contract claim; request one serialized P0-M2
row with the exact tested commit and live blockers. Keep #53 open pending real consent,
contents/attachment and notification evidence. Next independent source work can use
fixtures; WhatsApp131031 repair still needs actual account/business readiness and
authorized test-recipient scope. No new live send/model/deployment permission is implied.

## Offline verification

The new focused suite passes 32 mocked HTTP cases. Acceptance tests were written before
the implementation and initially failed on the missing module. A further backoff case
failed when a 9,999-second provider delay was shortened to 3,600; unsupported delays now
remain unknown and never create an invented earlier retry schedule.

Ruff lint/format and document formatting/whitespace checks pass. The final full backend
suite passes **423 tests**, with two existing dependency/test-key warnings, on a dedicated
disposable local Postgres instance. That server was stopped after validation. No web files
changed and no new web build or live provider evidence is claimed.
