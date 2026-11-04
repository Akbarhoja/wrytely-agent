# Telegram fallback boundary v1

A owns contracts/shared/transport; M owns authenticated HTTP/web/worker assembly.
Use the original Store, task/model runtime, budgets and course-supervision records.
Migration030 adds Telegram provider transport records only; no WhatsApp identity,
template, consent, outbox, business review or original gate is repurposed.

## Configuration and provider IO

Settings: telegram_bot_token, telegram_webhook_secret (SecretStr, defaultNone),
telegram_bot_username (public, defaultNone), standard AGENT_ prefix. Actual bot
is wrytely_agent_bot; key/secret are ignored local credentials, not repository data.
Derive bot_id ONLY with integrations.telegram.bot_id_for_token(configured_token);
never take bot/owner/chat IDs from browser input. getMe has independently confirmed
the newly created identity; no webhook or send is enabled by that metadata check.

Authenticate Telegram callbacks with verify_webhook(configured_secret, header)
before decoding the body. Header is X-Telegram-Bot-Api-Secret-Token, random32+
URL-safe characters. Bound actual received body to64KiB, not just Content-Length.
Reject duplicate credential headers. Then parse_update(payload) returns
TelegramText or None. Only original private text with chat.id==from.id, is_bot=false,
valid numeric IDs and timestamps within24h/+5min is accepted. Groups, edited messages,
callbacks and unsupported media do not become agent requests. No raw payload/token
or credential-bearing HTTP exception URL in logs. Authenticate even ignored updates.

TelegramAdapter(token,httpx_client).send(recipient=str(chat_id),text,action_id)
uses official HTTPS Bot API only, TLS verification, no redirects and one20s attempt.
Set HTTPTransport(retries=0); never log exceptions/settings/token-bearing request URLs.
Adapter redacts the standard httpx/httpcore request-log paths. Text is literal, no
parse_mode; disable previews/protect content. Over4096UTF16 units becomes a complete
inert UTF8 .txt attachment, never silently truncated. Max24000characters. This is
not a checked coursework/DOCX artifact. Confirm bot/sender/chat/message IDs before
recording acceptance. Accepted is NOT recipient delivery/read evidence. Timeout,
5xx, unexpected redirect/malformed receipt =>unknown; no automatic resend. Only an
explicit structured429 rejection may defer. No paid broadcast options are set.

## Existing Store methods

- create_telegram_challenge(verified_user,bot_id) -> message/expires_at. Message is
  /start followed by a43-character token.10min, one use, hashed at rest, rotates older
  challenge. Only verified session owner may request it. Existing link must be
  unlinked first. Return no-store. UI can form a t.me link using trusted configured
  public username and token, or let the user copy the exact private message.
- telegram_connection(verified_user,bot_id) -> linked/preferences/latest_delivery.
  Preferences is null or consent/notification_consent/timezone/quiet_start/quiet_end.
  Latest delivery is null or state/reason/created_at for the current link generation.
  No chat ID, generation, ingestion secret or raw token is exposed.
- set_telegram_preferences(verified_user,bot_id,*,consent,notification_consent,
  timezone,quiet_start,quiet_end) -> saved preferences. Both consents defaultfalse;
  Telegram consent must be explicit, not copied from WhatsApp. IANA timezone/hours;
  equal hours disables quiet hours only when explicitly saved by the student.
- unlink_telegram(verified_user,bot_id) removes this link/challenge and cancels
  unsent claims. History/unknown sends remain retained, not falsely undone.
- ingest_telegram(bot_id,authenticated_event) -> linked/queued/stopped/ignored/
  duplicate. Bot-scoped update-ID+digest replay fence and private-chat serialization;
  mismatched replay rejects. Unknown/unconsenting/paused senders do not create work.
  Pairing secrets never enter message/model history. Ordinary text reuses original
  Store.enqueue atomically, with existing20-job queue cap. /stop pauses the original
  agent, revokes existing task leases via set_paused, disables Telegram consents and
  cancels unsent Telegram actions. /start without a valid code and other slash
  commands are ignored in v1; no fabricated /accept, /file or revision support.

## Durable recovery and one-use dispatch

pending_telegram_preparations(bot_id,limit=20) returns internal owner/monitor/record
recovery hints only. queue_telegram_preparation(verified_user,bot_id,supervision_id,
preparation_id) rechecks explicit consents, original private status/current pins and
stores exact quote/checklist/questions/gaps. Key is record+linkgeneration; repeated
requests recover the same intent. Course/account pause, changed scope/source/age or
revoked link blocks it. No full-draft readiness/policy/citation gate is relaxed.

queue_telegram_replies(bot_id,limit=20) recovers completed replies from the existing
task journal into this provider outbox. It never invokes a second model, touches
academic tasks, or queues an old link generation. Oversized results are not truncated.

Worker sequence: recover hints/queue replies; claim_telegram_delivery(bot_id) ->
TelegramClaim|None; authorize_telegram_dispatch(claim) -> TelegramPermit with state
permitted/held/cancelled; ONLY permitted content may go to adapter once, using the
claim bot/chat and action_id. Then finish_telegram_delivery(claim,result) persists
the actual provider outcome with the same fence. Never send from an HTTP request,
UI render, model-generated recipient or arbitrary body. No provider IO under a DB lock.

Authorization repeats ownership, generation, consent, pause, current preparation
pins or exact completed reply,24h intent age, quiet hours and a3-per24h preparation
dispatch cap. It consumes the claimed fence before IO. Claims last60s; expired
undispatched claims can recover, but expired sending becomesunknown and never retries.
Only explicit provider rejection may retry up to3 dispatches; all recheck controls.
An already in-flight call cannot be unsent by pause/unlink. Retain actual outcomes.
The service must bind adapter.bot_id to the configured bot and reject mismatches.

M wires and tests existing auth/private proxy, pairing/preferences/status UI,
secret-authenticated callback and explicit worker entrypoint. No new runtime/model
worker, implicit resumption or budget refill. First activation must specify exact
candidate, migrations029–030, consenting recipient/data, budget and stop condition.
The proposed Telegram privacy addition needs owner review before publication/live use.
No live claim, graded draft/checked file command,24/7 operation or hackathon compliance
is proved by fixtures. Telegram is a disclosed fallback, not WhatsApp proof.
