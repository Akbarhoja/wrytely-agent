# Telegram academic delivery v1

Candidate only. A owns shared/contracts and this new Telegram adapter extension;
M owns app/worker/web assembly. Additive032 extends the original Telegram outbox
with offer/artifact/command kinds;031 and032 require scoped deployment approval.
No live send, model execution, consent or migration is activated by this code.

## Worker sequence

Keep the existing preparation/reply recovery. Additionally call
`Store.queue_telegram_academic_actions(bot_id, limit=20)` before claiming. It
recovers current proactively authorized offers and fixed command acknowledgments.
It returns a count of queued/recovered hints, not accepted messages. Each queue
operation rechecks account/link/consent; a stale recovery hint grants no authority.
Unexpected persistence errors must stop the worker, not be acknowledged as success.

`claim_telegram_delivery(bot_id)` still returns `TelegramClaim|None`, now with an
optional `artifact_file_id`. All original identity/generation/content fields stay.
Call `authorize_telegram_dispatch(claim, supports_documents=True)` only when the
worker can actually send checked documents. The default false holds document
intents without consuming a send, allowing old workers to remain fail closed.
Offer, preparation, command and ordinary reply permits have `payload=None` and
literal `content`. Use the existing adapter.send once.

For a permitted artifact, `TelegramPermit.payload` is an `ArtifactPayload`. Then:

```python
file = store.read_telegram_artifact_delivery(claim)
if file.descriptor != permit.payload:
    raise ValueError("Checked file changed")
receipt = adapter.send_document(recipient=str(claim.chat_id), file=file, action_id=claim.action_id)
```

This reads bytes only after the one-use dispatch permit has been consumed; it
rechecks owner, attempt/state/deadline, current link/consent/pause/quiet hours and
the original checked artifact/source/version proofs. Never fetch a public URL,
render an arbitrary worker-provided document or use the model to choose a recipient.
The adapter accepts `ArtifactDeliveryFile`, verifies exact digest/length/name/MIME,
and uses official sendDocument once. Responses use existing accepted/failed/unknown/
structured429 semantics. Accepted is provider acceptance, not delivered/read.
Persist with original `finish_telegram_delivery`; false means unknown, never success.

## Intent creation and authorization

- `queue_telegram_offer(user,bot,supervision_id,offer_id)` requires both Telegram
  consent flags plus the original course proactive consent and current complete
  pinned offer. It includes exact `/accept UUID` and `/decline UUID` instructions.
  Recheck at dispatch; changed sources, paused course, declined offer or revoked
  notification consent cancels. Offers and preparations share three dispatches/day.
- Original command receipt recovery creates fixed acknowledgments only. Rejections
  never echo provider/source/revision text. It references the same bot/update/owner/
  link generation and compares the saved receipt again before sending. No model call.
- `enqueue_telegram_artifact_delivery(user,bot,artifact_id)` requires explicit
  student request and current checked artifact. `/file ARTIFACT_UUID` composes this
  method inside the original inbound transaction. It reuses original immutable
  `artifact_delivery_files`, never creates a WhatsApp link/action. One file intent
  per artifact is recovered even after relink, so an unknown/accepted outcome is
  never turned into a new attempt by repeating `/file`. A distinct revision has a
  distinct artifact/file and can be requested separately.

All intents share the existing outbox leases, consent/pause/unlink fencing, age,
quiet hours and single-dispatch transitions. Unknown sends do not retry. An already
in-flight send cannot be undone by a later control change. Delivery worker failures
must preserve that uncertainty. Full graded work still requires original policy,
source coverage, student delegation and checked-artifact gates; a checklist is not
promoted to a checked Word file.

Automatic discovery/notification of newly ready draft artifacts, natural-language
delegation, callback buttons and timed quiz work are not added by this boundary.
This completes explicit file-request transport, not proof of an always-on product.

## Requested Word-file export

Checked DOCX delivery fulfills an explicit owner request for a usable file. The
adapter sends these Word documents with Telegram `protect_content=false`, allowing
the recipient to save/export their copy. Ordinary messages and long checklist TXT
attachments retain `protect_content=true`. This does not create a public download
URL or bypass the original owner, consent, checked-byte, source and receipt gates.

Provider reference: [Telegram sendDocument](https://core.telegram.org/bots/api#senddocument).
