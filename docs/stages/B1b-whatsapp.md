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
No API access token is consumed yet: outbound delivery is deliberately inactive.

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
No worker calls this adapter automatically yet; no real messages were sent.

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
- Implement a durable delivery worker with crash/unknown handling, current
  permissions, quiet hours, conversation-window enforcement and approved templates.
- Consume authenticated delivery status callbacks and retain accurate evidence.
- Validate media intake separately; this stage handles text only.
- Configure usage limits, consent and operational logging before a public pilot.

Do not set queued records to delivered or blindly resend after an uncertain send.
The adapter's accepted state means provider acceptance only.
