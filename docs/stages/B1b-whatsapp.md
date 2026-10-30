# WhatsApp integration — development setup and remaining acceptance

Implemented: signed webhook validation, business/phone filtering, authenticated
single-use ten-minute linking challenges, number ownership uniqueness, durable
inbound IDs, transactional task creation and reply outbox, unlink cancellation.
These are development APIs, not evidence of a working live WhatsApp connection.

## Meta setup

Use a development Meta app with the WhatsApp product and its test number. In Meta's
current dashboard follow the WhatsApp API setup instructions; configure the API
with the app secret, a separately generated webhook verification token, phone
number ID and WhatsApp Business Account ID. See `.env.example` for names. Supply
secrets locally or through hosting secret controls; never paste them into chat.
Outbound delivery runs only when the explicitly configured delivery worker below
is started. The API/model worker does not dispatch messages itself.

## Murtazo delivery transport increment — October 28

`WhatsAppAdapter.send_template` prepares a single Cloud API request for a static
template or positional body text parameters. It validates recipient/template/
language syntax and nonblank parameters before HTTP. Parameters are conservatively
limited to 1,024 characters each by the application. Header, button, named and
media parameters are outside this increment. Existing text sending is preserved.

The caller must choose a configured, approved and enabled template, check its
parameter count/schema, and enforce permissions and timing. This transport alone
does not establish those checks. Reference payload:
https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/messages/template/

Both paths use the same single-attempt receipt classification: acceptance retains
the provider message ID, explicit rejection is failed, and a lost response or
malformed success is unknown. Injected HTTP transport must have retries disabled.
At this initial transport-only checkpoint no worker called the adapter. The later
text-reply integration is described below; no real messages have been sent.

Validation on Windows/Python 3.12: 24 transport tests passed, including 14 new
template cases. Full backend run: 46 passed and 45 setup errors, all because no
isolated `AGENT_TEST_DATABASE_URL` is configured and macOS-only `pgserver` is
unavailable. Full database regression validation remains outstanding. The locked
dependencies also emit existing Starlette/httpx and short test HMAC-key warnings.
Shared delivery state, preferences and concurrency contracts await agreement in
issue #4; runtime/shared/schema files were not changed.

Continuation: callback parsing now validates the configured business/phone envelope,
provider reference, recipient, supported status and provider epoch time. A mixed
batch retains valid rows while ignoring malformed rows. Original provider epoch is
preserved; future skew above five minutes is rejected. This pure parser assumes
raw-body authentication and does not itself mutate delivery state.

Full regression validation is now unblocked: an isolated password-protected EDB
Postgres 17 instance in a temporary ASCII Windows path listens only on loopback.
All 118 backend tests pass (51 transport tests); Ruff lint/format/diff checks pass.
The two existing dependency/test-key warnings remain. No production data or live
provider was used. The earlier 45 fixture errors describe the initial setup only.

Apply migrations only to the designated development database using
`python -m app.migrate`. Set the webhook URL to an HTTPS development deployment's
`/webhooks/whatsapp`, verify it, and subscribe to message events. GET verification
and POST signature authentication use distinct secrets. Avoid logging webhook
bodies or verification query strings in deployment access logs.

## Durable text-reply worker and callback assembly

This feature branch stacks on the complete memory (#7) and delivery storage (#9)
dependencies, including migration 005 and the token/version Settings addition.
Those shared changes remain Akbar's work and are not claimed as Murtazo's
implementation. Land/review the dependency chain in order before integration.

`integrations/whatsapp_delivery.py` claims a saved action, obtains a fresh one-use
authorization, sends only the returned authoritative payload, and records actual
transport evidence. It never replays an authorization. A crash or result-storage
failure leaves the persisted attempt to expire to unknown without automatic
resend. A pause/unlink after dispatch authorization cannot recall an in-flight
request; the DB decision and Meta request are not atomic.

The existing signed webhook now also persists delivery statuses using configured
account/number, provider reference and recipient. Original event timestamps keep
replay identity stable. Early callbacks are reconciled by the existing Store;
storage rejection returns 503 for replay instead of acknowledging lost evidence.
Text timestamps are recorded only after durable inbound ingestion; missing or
invalid timestamps do not establish conversation-window eligibility.

Authenticated `POST /v1/whatsapp/preferences` accepts exactly:

```json
{"consent": true, "timezone": "America/Denver", "quiet_start": 22, "quiet_end": 7}
```

Account identity comes from the verified session. Consent must be an explicit
boolean, timezone a valid IANA name, and hours integers from 0 to 23. Equal hours
disable quiet hours explicitly. The website/proxy preferences UI remains later
onboarding work. No preferences or permissions are inferred for existing accounts.

Configure `AGENT_WHATSAPP_ACCESS_TOKEN` and `AGENT_WHATSAPP_API_VERSION` securely
alongside the existing database/business/number settings. The version must be an
explicit supported `vN.0`; the worker has no version default. Do not paste tokens
into command arguments or logs. After reviewing/applying migrations to the
designated development database, start the API, model worker, and separate delivery
worker. The delivery worker never applies migrations:

```sh
uv run --env-file .env python -m app.whatsapp_worker --once
uv run --env-file .env python -m app.whatsapp_worker
```

`--once` processes at most one candidate and exits; it can send a real message
when credentials/actions are live, so it is not a dry-run flag. The process uses
one HTTP client with transport retries disabled, a 15-second timeout, redirects
disabled and environment proxies disabled. Ctrl+C closes the client. Unexpected
iteration errors log a fixed code without exception text or message content.

Expired windows still hold with `approved_template_required`: template transport
alone does not authorize proactive sending. Approved template selection/payload
configuration remains a shared-contract follow-up. A live Meta-powered round trip
and public deployment remain unverified.

Current integrated validation: 175 backend tests pass against isolated local
Postgres, including worker concurrency/restart, post-send storage failure, signed
callback-before-response/replay/order handling, private preferences and incorrect
recipient isolation. Ruff lint/format and diff checks pass. Existing Starlette/httpx
and short synthetic HMAC-key warnings remain. This is offline simulated transport
with real storage, not real provider evidence. The shared-storage orphan-capacity
edge case reported in #4 was fixed by Akbar's track in commit `d61217b`. This
feature branch now consumes that fix and its three storage regressions: known
exact-match callbacks bypass orphan-only capacity, while new unmatched/wrong-
recipient evidence remains capped. This remains Akbar's shared-storage contribution.

## Link and ingest

After verified Clerk signup and bootstrap, authenticated
`POST /v1/whatsapp/link` returns a `message` beginning with LINK. Send that exact
message from the student's WhatsApp number to the development business number.
The challenge is stored hashed, expires after ten minutes, is replaced on reissue,
and is consumed once. The linking text never becomes model context. Unknown
senders get no private information or automatic response.

Subsequent text messages create one private task per provider message ID. Provider
retries are safe. Queue-full returns 503 so unaccepted work can be retried. A
completed WhatsApp task saves one outbound record atomically with its result.
Website tasks do not automatically generate WhatsApp messages.

Authenticated `POST /v1/whatsapp/unlink` clears linking challenges and cancels
queued/deferred sends. In-flight requests cannot be unsent. A later link does not
receive replies from tasks accepted under a previous link.

## Remaining before enabling sends or claiming M1

- Configure a live development Meta model and WhatsApp test number; verify the
  entire signed-in student → verified number → task → model result path.
- Add the student's linking/status controls and backend proxy route allowlist.
- Review the durable text-delivery path and shared dependency PRs, then agree the
  approved-template authorization/configuration contract for proactive delivery.
- Validate signed callbacks and current-permission checks with a real provider.
- Validate media intake separately; this stage handles text only.
- Configure usage limits, consent and operational logging before a public pilot.

Do not set queued records to delivered or blindly resend after an uncertain send.
The adapter's accepted state means provider acceptance only.
