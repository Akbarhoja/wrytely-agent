# WhatsApp delivery: proposed claim and interface request

Prepared October 28, 2026. Posted with Murtazo's authorization:

- Claim: https://github.com/Akbarhoja/wrytely-agent/issues/5#issuecomment-6481056367
- Interface request: https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6481060467

The comments below retain their original wording as a record of the proposal.

## Proposed comment on work item #5

Owner: Murtazo (`murtazokhon-tech`), working with his local coding assistant.
Work item: #5. Branch: `murtazo/whatsapp-delivery`.
Base: `codex/team-integration`.

I acknowledge the ownership and coordination workflow in #4. Proposed file claim:

- `integrations/whatsapp.py`: extend the existing transport for approved templates
  and bounded, account-filtered status-event parsing.
- `integrations/whatsapp_delivery.py` (new): delivery orchestration using the
  agreed existing-store interface; no separate database client.
- `app/whatsapp_worker.py` (new): delivery process assembly and lifecycle.
- `app/main.py`: signed status callbacks, only after the shared contract agrees.
- `tests/test_whatsapp.py`, `tests/test_whatsapp_delivery.py` (new),
  `tests/test_whatsapp_flow.py`: transport, orchestration and agreed API checks.
- `docs/stages/B1b-whatsapp.md`: development setup and actual acceptance evidence.

Acceptance: one claim wins under concurrency; restart cannot blindly resend an
uncertain attempt; current link, pause/cancellation, timing and permission checks
gate sending; expired windows require an approved template; unknown preferences
hold sending with a reason; signed callbacks are replay-safe, account-scoped and
cannot regress delivered state. Offline tests and live evidence stay separate.

Dependencies: Codex-owned shared storage/schema/configuration and contract
agreement in #4; development Meta setup for later explicitly budgeted live tests.
No shared/runtime edits or live sends are claimed. Implementation has not started.

## Proposed comment on coordination issue #4

@Akbarhoja Murtazo is starting #5 on `murtazo/whatsapp-delivery`. Please confirm
the file claim in #5 and agree the shared delivery boundary before dependent code.
The proposal below is a request, not an implemented contract.

Ownership: your runtime track implements shared storage, schema, settings and
contract types/tests. My integration track implements transport, worker assembly,
callback assembly and messaging tests. Please confirm ownership of cross-layer
tests before either track edits them.

Proposed boundary:

1. `claim_whatsapp_delivery(worker_id)` returns no work or a fenced delivery
   claim with action/agent/task IDs, current verified link identity, recipient,
   payload, attempt token and deadline. Persist the claim atomically. Resolve
   abandoned sending attempts as unknown; never automatically queue them again.
2. `authorize_whatsapp_send(claim)` rechecks lease, current link generation,
   pause/cancellation, consent, source/result validity where applicable, timezone,
   preferences and conversation window immediately before dispatch. Return a
   permitted text/template payload, a persisted hold with reason/retry time, or
   cancellation. Specify the control-change/dispatch race boundary honestly.
3. `record_whatsapp_result(claim, result)` accepts only the owning attempt and
   persists accepted/failed/unknown evidence plus provider reference. Provider
   acceptance never implies recipient delivery. No blind retry on unknown.
4. `record_whatsapp_status(event)` matches configured business/number, provider
   reference and recipient against a persisted action, not a caller's account ID.
   Apply an agreed transition table idempotently; delayed/repeated callbacks cannot
   regress delivered state. Agree handling for a callback arriving before the
   send response is persisted, including correlation and orphan reconciliation.

Data/configuration needs: attempt fencing/timestamps, link generation, unique
provider-reference lookup, hold reason/retry time, delivery event evidence,
persisted timezone/quiet hours/communication consent, and approved template
configuration with language and parameter validation. Missing required data must
hold sending. Existing `last_inbound_at` uses receipt time; agree trusted inbound
event-time semantics so delayed webhook delivery cannot reopen an expired window.

Errors: stale claim/control revocation must prevent a new dispatch; storage failure
must not be treated as success; uncertain provider or post-send persistence failure
must remain reconcilable without automatic resend. No secrets in logs or issues.

Migration: add a new ordered, additive migration in `wrytely_agent`; preserve
001–003. Backfill existing replies conservatively and never infer consent or
timezone. Development/test databases only; no production migration requested.

Please confirm or amend the names, payloads, transitions, migration ownership and
test split. While agreement is pending, transport/parser work can proceed only
after the #5 claim is recorded and checked for overlap.
