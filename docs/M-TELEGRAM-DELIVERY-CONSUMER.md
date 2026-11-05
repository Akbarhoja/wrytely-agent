# M Telegram academic delivery consumer

Post-submission candidate, claim
[6649206861](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6649206861).
M owns `codex/telegram-delivery-consumer`; A retains final integration and all
runtime/shared/contracts/provider/collector ownership. The branch composes A08aee7d
with corrected M9b397e9 preserving authorship. No submitted build is overwritten.

## Composition

The existing worker keeps preparation/reply recovery, adds the published academic
recovery selector, and requests document support explicitly during authorization.
Only an `ArtifactPayload` permit can enter checked-file dispatch. The worker then
reads the fenced immutable file, compares its descriptor exactly and invokes the
published adapter's `send_document` once. Literal text still uses `send`. No URL
fetch, rendering, model-selected recipient, parallel Store or new outbox exists.
A failed descriptor/control read or unexpected dispatch exception is retained as
unknown; a false receipt-persistence fence never becomes a success or retry.
Original source/checked-artifact/policy/link/consent/pause gates remain authoritative.

The private Telegram panel consumes current-link `latest_command` when supplied
by the server. It projects only fixed applied/rejected labels and a timestamp.
Nested result bodies, revision instructions, target IDs and arbitrary error text
are not rendered. Missing fields remain compatible with the old backend; malformed
receipts fail closed and clear private state. Account/session/unlink state changes
clear receipts. There is no UI-triggered dispatch or retry. A recorded command is
not a claim that work completed or a file reached the recipient.

## Candidate support versus live capability

A's current source adds explicit `/accept OFFER_UUID`, `/decline OFFER_UUID`,
`/revise ARTIFACT_UUID instructions` and `/file ARTIFACT_UUID` to the existing
secret-authenticated callback. The callback needs no new parser or route. This
consumer adds offer/acknowledgment/file recovery and dispatch only through A's
published permits. It does not infer an implicit/latest target, add callback
buttons, change source scope, start a paid worker or promote a checklist to a
checked coursework artifact. Automatically announcing newly completed artifacts
and unbounded continuous operation remain outside this boundary.

These are source-code capabilities, not deployment or live receipt evidence.
Migrations031–032, the updated backend/worker and any actual data/sends require
separate owner activation. Earlier approved operations proved pairing and stopped
before outbound; no later paid/send proof is inferred. Existing budget liabilities
and all unknown outcomes stay preserved. Provider accepted does not mean delivered
or read. All rehearsal providers/models are scripted.

## Reproduce the intended checkout

Follow [local setup](../deploy/LOCAL-SETUP.md), selecting
`codex/telegram-delivery-consumer` instead of the earlier app-fix branch, and record
the exact reviewed SHA from its PR. The matching migration ledger includes031–032.
A preflight is read-only by default; do not use missing migrations as permission to
migrate a retained database. Existing explicit `app.telegram_worker --once` or
bounded `--run` entrypoints remain operator-only under concrete scope/recipient/
attempt/stop approval. This document runs nothing and changes no credentials.

## Verification scope

Focused document-worker/adapter/Store checks cover exact bytes, one-use permits,
changed descriptors/controls, uncertain transport and restart without duplicate
file delivery. Private UI tests cover fixed labels, malformed data and account
clearing. The connected rehearsal uses authenticated TestClient callbacks, original
Store transactions and an actual TelegramAdapter with MockTransport: acceptance
recovers one stable work intent; an explicit file request sends synthetic checked
bytes plus its fixed acknowledgment; replay sends nothing again; revision creates
its original queued intent and a privacy-safe acknowledgment. It does not prove a
new completed revision, real model quality or actual phone receipt.

Record final exact counts/CI in the PR. Required complete backend/web checks and A
review are separate from focused success; no previous candidate green is transferred.
