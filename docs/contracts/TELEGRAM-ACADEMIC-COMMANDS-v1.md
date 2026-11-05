# Telegram academic commands v1

A-owned continuation from the reviewed Telegram fallback, not a live activation.
Additive031 adds nullable `command_result` to the original Telegram inbound receipt.
No independent command queue, identity resolver, model runtime or WhatsApp link.
Apply031 only after scoped deployment/migration approval. Older executables remain
compatible with the additive column; this executable requires the migration.

## Ingress and exact targets

The existing secret-authenticated, private-chat callback passes original text to
`Store.ingest_telegram`. It now recognizes:

```text
/accept OFFER_UUID
/decline OFFER_UUID
/revise ARTIFACT_UUID explicit instructions
```

UUIDs must be explicit canonical UUIDs from the student's own work; do not resolve
"latest" or a model-provided owner. The parser never invokes a model. Revision
instructions are required and bounded at4000characters. Extra acceptance arguments,
missing targets and malformed recognized commands are permanently rejected. Unknown
slash commands remain ignored and never enter generic chat, including leading-space
slash commands. `/file` is still unsupported. `/stop` keeps its existing exact command
semantics. Bot-suffix commands, buttons, reply-to inference and natural-language
delegation are not implemented by this version.

The original bot/update digest replay fence, chat lock, linked owner, current link
generation, event age, paused state and explicit Telegram reply consent apply first.
Notification consent is not substituted for a student's explicit command consent.
No consent or other user's chat means ignored, with no academic work. Cross-account
targets produce a generic unavailable result and disclose no target details.

## Atomic work and receipts

`ingest_telegram` additionally returns `command_applied` or `command_rejected`.
Its public HTTP callback still returns only a state, never a private command result.
The existing callback needs no alternate parsing or worker to create this intent.
Within the original transaction, acceptance invokes the existing scoped offer
decision and stable-key Canvas responsibility creator. Decline creates no work.
Revision invokes the existing checked, current, private artifact revision method
with a bot/update-namespaced request key. Source freshness/policy/rubric/checked
artifact requirements and budgeted asynchronous execution remain unchanged.

Known business rejections roll back partial changes using a savepoint and persist
a rejection receipt. Unexpected database/runtime failures roll back the entire
ingestion so exact provider replay can recover; no success is acknowledged. A
duplicate update returns `duplicate` and never applies work again. Different text
under the same update raises the existing replay conflict. Repeated acceptance
with a new update recovers the original stable-key responsibility.

Private `telegram_connection(user, bot)` adds `latest_command`: null or
`{outcome, command_result, received_at}` for this owner and current link generation.
It exposes no Telegram chat/update IDs, linking secret or revision instructions.
Applied results include kind, exact target and the existing duty/revision result;
rejections expose fixed reasons only. Unlink/relink hides earlier-generation receipts.
Historical receipts are not a grant to read an artifact after scope changes.

No immediate bot acknowledgment, offer notification, document dispatch, automatic
result delivery, paid worker activation or complete student journey is added here.
M owns that app/transport/UI assembly. Accepted work still requires separately
authorized model execution; private checked file delivery needs its own typed
Telegram dispatch contract. Existing WhatsApp commands are unchanged.
