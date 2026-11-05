# Telegram app assembly candidate

M consumer of [A Telegram v1](../docs/contracts/TELEGRAM-v1.md), assembled on
`codex/telegram-assembly` from reviewed M PR172 and A588c504, preserving authorship.

Existing authenticated private proxy now permits only GET telegram and POST
telegram/link, telegram/preferences, telegram/unlink. Identity comes from verified
sessions; configured token supplies bot identity. Pairing messages are private,
one-use and expire; the UI never stores them. Both Telegram permissions start false.
Explicit saves set IANA timezone/quiet hours. Unlink cancels unsent work through the
original Store. Account/session changes clear private panel state. Browser UI and
callbacks never invoke models or send to Telegram.

Public POST /webhooks/telegram verifies exactly one secret header before reading
at most64KiB of JSON. Private original text enters the original Store/task queue
only through A's authenticated parser and replay boundary. No callback registration
or public exposure is performed by these code changes.

Explicit operator entrypoint: `python -m app.telegram_worker --once`, or bounded
`--run --max-iterations N --stop-file PRIVATE_PATH`. Requires separately authorized
development environment and recipient/scope. This code never migrates or grants
model budgets. Worker preserves configured Canvas origins, requeues only original
eligible intent recovery, checks bot identity, consumes a one-use dispatch permit,
and attempts provider IO once. Exceptions become unknown; restart never blindly
resends. A's Store alone controls structured429 bounded deferral. Accepted does not
mean recipient delivered/read. No new model runtime/queue.

Deployment, migrations029–030, token/webhook setup, privacy notice publication,
real student data transfer and live sends require their own explicit owner approval.
Do not use this document as an activation command. Secrets stay private.
Telegram v1 only supports preparation text/inert long TXT and ordinary replies.
It does not implement /accept, /file, /revise, checked-coursework file delivery or
full WhatsApp equivalence. WhatsApp remains separate/inactive, not marked complete.

Initial local61 adapter/Store/HTTP/worker checks PASS with disposable Postgres and
scripted provider. Full web, exact combined full backend CI and counterpart review
are required before acceptance; record actual results in the PR. No live proof.

## Academic delivery continuation

The original v1 limits above describe that earlier implementation. The later
[academic delivery consumer](../docs/M-TELEGRAM-DELIVERY-CONSUMER.md) consumes A's
031–032 command, offer, fixed acknowledgment and checked-document interfaces on a
separate post-submission candidate. Code support does not establish installed/live
capability. Use its exact reviewed checkout and matching ledger; no migration,
worker start, provider call, scope change or send is authorized by this note.
