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
