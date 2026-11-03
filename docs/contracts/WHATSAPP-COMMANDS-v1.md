# Signed explicit WhatsApp commands v1 — implementation candidate

A owns shared Store/contracts/028; M owns bounded explicit-command parsing and
webhook routing, raw signature/account validation and actual provider transport.
No model classifies or authorizes these commands. No new provider call or live grant.

## Executable handoff

`Store.execute_whatsapp_command(envelope, business_id=trusted_config,
phone_number_id=trusted_config) -> receipt`

`contracts.whatsapp_commands.WhatsAppCommandEnvelope` exact fields:

```json
{
  "provider_id": "synthetic-incoming-id",
  "sender": "15555550123",
  "event_at": "2026-11-03T23:00:00Z",
  "business_id": "synthetic-configured-business",
  "phone_number_id": "123",
  "reply_to_provider_ref": null,
  "command": {
    "kind": "accept_offer",
    "target_id": "00000000-0000-4000-8000-000000000001",
    "instructions": ""
  }
}
```

Allowed kinds: accept_offer/decline_offer (owned course offer), revise_artifact/
send_artifact (owned current checked v2 artifact). Only revise_artifact accepts
instructions, explicit nonblank<=4000characters. UUID target may be omitted ONLY
with the authenticated provider reply context. When both are present they must
identify the same object. No user_id/agent_id/recipient/permission/ready fields.
The example is synthetic, not an executable grant or proof of signature.

M authenticates exact raw webhook bytes first and filters configured business and
number. Sender/provider ID/timestamp/context.id come only from that signed payload;
the parser supplies only a recognized explicit command, target and student feedback.
Missing timestamp/context or ambiguous natural language must not be converted into
an acceptance. This method is INTERNAL, not a browser/student RPC. Never use a
model-generated command, synthetic signature flag or lookup-owner-by-phone endpoint.

## Ownership and transaction

The Store resolves the current link/owner internally, serializes provider ID/sender/
agent, rechecks link generation and rejects mismatched account. Events must be<=24h
old,<=5min future and not predate the current link (provider-second precision).
Unknown/unlinked senders return `{state:ignored}` without retaining instructions.

A reply target must match an original typed outbox offer/document, account/number,
recipient/current link generation, dispatch time and accepted/delivered/unknown
state. Generic chat references, unrelated/stale link references and explicit target
conflicts reject. For send/revise replies to an ACCEPTED original offer, resolve
only its stable course-offer responsibility and latest v2 artifact, with no academic
work still pending/running. An explicit artifact ID must belong to that same duty.
This lets the student ask for their first file from WhatsApp without looking up an
artifact UUID on the website. Unaccepted offers, unfinished/no-result work and
unrelated artifacts reject; no global latest-offer/artifact guess. Existing current
source/pause/policy/check gates still apply when executing the file/revision action.

The ORIGINAL whatsapp_inbound row stores normalized command, digest, current link
generation and receipt; task_id staysNULL. Existing Store decision/delegation,
revision and file-enqueue methods compose under one private transaction context.
No generic conversation message/reply task, second inbound queue or parallel runtime
is created. Context is per Store and execution/thread, not a global shared connection.
Savepoints roll back partial acceptance/work on an expected business rejection;
the rejection receipt remains. Unexpected persistence errors roll back the entire
receipt/action together, so provider replay can safely execute the original command.
No retained database is migrated automatically.

Acceptance creates only the original scoped responsibility; decline creates none.
Revision uses stable incoming-event request key and immutable checked pipeline.
Send enqueues one original typed file action; it never sends directly, overrides
communication consent, quiet hours, window, pause or current evidence checks.
Offer pending acceptance expires after24h; replay of an already recorded result
does not grant another action. Model/delivery workers remain separate and stopped.

## Receipts and webhook behavior

Successful receipt: `{state:applied,kind,target_id,result,replayed:false}`.
Result is the existing bounded responsibility/revision/action identity/state.
Expected rejection: `{state:rejected,kind,reason,replayed:false}`; reason is safe
agent_paused/command_context_unavailable/source_refresh_required/command_unavailable.
Exact event replay under the SAME current link/account returns the saved receipt
with replayed:true, even after later source/control changes: historical acknowledgment,
not permission to execute or send again. Changed event body, different current link
or collision with a previously generic inbound event raises
WhatsAppCommandRejected(command_replay_conflict). Bad account/expired event also
raises that safe exception; unknown sender is ignored without retention.

M routes recognized commands to this method INSTEAD OF ingest_whatsapp. Do not call
both for one incoming event or turn rejected commands into generic model requests.
Generic messages and LINK continue through original ingestion. Already committed
command IDs are duplicates there, preventing delayed generic replay. Original
command intake updates last_event_at from the authenticated provider time itself;
receipt time never opens a conversation window. Expected rejection/permanent envelope
errors may be acknowledged without a send; unexpected DB errors must not be
acknowledged as stored. No automatic model retry or outward command acknowledgment
is implemented by this Store method. M's signed webhook tests prove the signature
assembly separately from these synthetic-envelope Store tests.
