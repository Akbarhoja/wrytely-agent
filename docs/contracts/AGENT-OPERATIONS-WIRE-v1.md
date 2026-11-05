# Agent operations wire v1 — C4–C7 review candidate

Owner A; consumer reviewer M. Tracks [P0-A3](../WORK-ORDERS.md#p0-a3--freeze-interfaces-and-operational-limits-a)
and [the existing action architecture](AGENT-ACTIONS-v1.md).
**Proposed, not agreed, implemented or permission to activate.** No live budget,
provider permission, worker, student delegation or production configuration changes.
This supplement supplies exact first-version boundaries for counterpart agreement.

## Existing implementation and compatibility

Reuse `shared/delivery_store.py`, `shared/whatsapp_store.py`, `shared/artifacts.py`,
existing task leases, typed `contracts/delivery.py` and `contracts/templates.py`.
M's adapter, webhook signature verification, app/UI and deployment remain M-owned.
The current adapter loop sends completed reply text; it does not implement all the
payloads below. No consumer may pretend a new dataclass/API exists because it is
specified here. Keep current text/reply clients working until their explicit migration.

All proposed objects reject unknown keys, wrong types and bool-as-int. UUIDs are
canonical; timestamps strict aware RFC3339 normalized to UTC; textual bounds count
Unicode code points after LF/NFC normalization. Credential/link identities come from
verified sessions, signed provider ingestion or leases, never model parameters.
The model never supplies recipient, provider account, upload URL, storage path,
budget/price, artifact-ready flag or consent. Private responses/errors use no-store.

## C4: persist action, authorize once, record evidence

Internal methods (not HTTP routes):

```text
propose_agent_action(lease, proposal) -> ActionReceipt
claim_agent_dispatch(worker_id, lease_seconds=60) -> DispatchClaim|null
authorize_agent_dispatch(claim, trusted_channel_config) -> Authorization
record_agent_dispatch(claim, result) -> ActionReceipt
reconcile_agent_dispatch(verified_provider_event, trusted_channel_config) -> Receipt
```

Proposal is exactly:

```text
{schema_version:1,kind,goal_id,commitment_id,expected_commitment_revision,
 expected_memory_revision,evidence:[{object_id,observation_id,version_id}],
 purpose,work_mode,not_before,expires_at,content}
```

kind is offer_help/notify_change/request_refresh/schedule_check/wait. goal_id and
commitment_id are owned UUIDs or null; revision integer>=0 or null exactly when its
associated ID is null. purpose is a controlled identifier1–64; evidence0–20 pinned
owned references; version_id nullable for explicit gaps, never fabricated text.
work_mode is null or private_draft (only offer_help). content is normalized text
1–4096; timestamps mandatory with not_before<expires_at. Outbound actions expire within24h;
schedule_check/wait may choose a due time within the C7 seven-day horizon and expire
at most one hour after that due time.
schedule_check/wait create no outbound dispatch. The remaining agent tool sequence
uses existing task contracts; this does not add a run-shell/submission action.

The server chooses action_id and dedup identity from owned commitment/goal, purpose,
relevant revision and intended occurrence. A model cannot mint a new dedup key to
repeat an offer. Evidence must be currently accessible, scoped, sufficiently fresh
and complete for the claim, including latest failed checks. A missing/partial source
can justify an honest request_refresh; it cannot justify a claim about unseen work.
Re-reading unchanged evidence returns the existing action. No goal/course crossing.

ActionReceipt is exactly `{schema_version:1,action_id,state,reason,replayed}`;
reason is a controlled code or null; replayed bool. Public projection excludes text,
recipient, channel account and tokens. States are queued/held/dispatching/accepted/
delivered/unknown/failed/cancelled. These are proposed projections: map current
DB deferred→held and sending→dispatching; do not rename existing rows/consumers.
read provider evidence can enrich delivered; it never implies assignment submission.

DispatchClaim contains exactly schema_version,action_id,attempt_token,worker_id,
lease_until,agent_id,link_generation. Claim alone contains no reusable send authority.
A locks the owning agent, then outbound action, then capability/quota rows in the
same consistent order as controls. Check current generations/revisions, consent,
pause, expiry, quiet hours, source readiness and adapter capability at authorization.
No queue-time approval substitutes for this check.

Authorization is an exact discriminated union:

```text
{schema_version:1,state:"held"|"cancelled",reason,retry_at}
{schema_version:1,state:"permitted",action_id,attempt_token,dispatch_id,
 link_generation,expires_at,recipient,payload}
```

Only trusted M assembly receives permitted recipient (the current linked student's
number); model/public projections never do. dispatch_id is server-issued, one-use,
bound to attempt/link/payload SHA256, expires min(claim deadline,now+30s).
`authorize_agent_dispatch` itself locks and rechecks the current action/attempt, then
atomically consumes the one-use authorization and records dispatch_id, payload digest,
dispatch_at and the applicable quota reservation. Its database transaction MUST commit
successfully **before it returns state=permitted** to M. There is no separate M-owned
consume step, and M performs no network IO until that committed permitted result.
This matches the existing authorize_whatsapp_send transaction boundary.

A second authorization call for that consumed attempt cannot return permitted again:
raise the existing lease fence internally, mapped to controlled409 at any future HTTP
boundary. A crash or lost acknowledgment after consumption but before the caller sees
permitted is conservative dispatch uncertainty; it does not permit another authorize/
send attempt. Reconcile the immutable dispatch identity without creating fresh authority.
The returned dispatch identity is not a bearer token exposed in URLs. An expired grant
cannot be refreshed and reused after an uncertain attempt.

Payload is one of these exact shapes, pending adapter agreement:

```text
{kind:"text",text}
{kind:"offer_buttons",text,buttons:[{id,label}]}
{kind:"document",file_id,artifact_id,artifact_revision,sha256,mime,filename,caption}
{kind:"approved_template",template_key,configuration_revision,parameters:[string]}
```

Internal limits: text4096, caption1024,1–3 buttons, button label20, opaque id128,
parameters at most10 of1024 code points. These are product bounds, not a claim of
current provider acceptance; M must validate actual provider/locale/template/media
constraints and reject unsupported payloads before dispatch. Button IDs are generated
by A and bound to C5, never a model-chosen offer/task identifier. Document delivery
requires C6 finalized identity. Template key/revision and parameter schema are trusted
operator configuration with actual provider approval; source text cannot choose them.

Text/buttons/documents require a trusted open reply window under the existing channel
policy. Outside it, only a specifically approved eligible template can be sent; a
student reply opens the relevant continuation. No approved template means held, not
raw text fallback. Existing reply-template configuration is not blanket proactive
approval. Keep exact model output out of parameters unless that template permits it.

Result is exactly `{schema_version:1,action_id,attempt_token,dispatch_id,state,
provider_ref,reason}`. state accepted/failed/unknown; accepted requires provider_ref,
failed requires proof of no delivery and a controlled reason; transport uncertainty
is unknown, never failed-by-default. A result matches exact attempt/dispatch; an
unrecognized result cannot mutate another action. Late receipts use immutable dispatch
identity and preserve current cancellation/control state; they cannot restart work.
Signed callbacks also match configured account, recipient, provider reference and
attempt mapping. Out-of-order/repeated callbacks are idempotent; conflicting evidence
is retained as a conflict, not reordered into a fictional outcome.

After dispatch_at is committed, lease expiry/crash/timeout never queues an automatic
second send. Reconcile accepted/delivered/unknown using trusted provider evidence.
An explicit retry is a separate audited intent, still subject to consent/dedup/quota;
no operator retry is performed by this proposal. A cancellation cannot recall an
already delivered phone message; report late delivery honestly.

## C5: student decisions bind an exact current offer

```text
apply_agent_decision(verified_actor, decision, replay_key) -> DecisionReceipt
```

For work decisions, exact body:

```text
{schema_version:1,kind:"accept_private_work"|"student_will_do"|"decline"|
 "snooze"|"request_revision",offer_token,expected_commitment_revision,
 delivery_to_self,snooze_until,revision_request}
```

offer_token is opaque server-generated >=192 bits entropy, stored hashed, bound to
owner/link/action/commitment revision, explicit allowed decision set and expiry
(min offer expiry,24h). Public bodies never contain user_id/recipient. Valid webhook
actor comes from the persisted signed inbound plus current link; web actor from the
verified session. A token alone cannot authorize a different actor/link. Free-text
Meta parsing produces this same candidate shape; uncertain yes/ambiguous offer causes
clarification. No model-confidence threshold substitutes for clear delegation.

delivery_to_self is bool, true only when accept explicitly includes returning the
result to the same linked student; other decisions require false. snooze_until is
an aware future timestamp<=7days only for snooze, otherwise null. revision_request
is1–2000 code points only for request_revision, otherwise null. A student-do/decline
cancels pending agent work for this obligation, not its private historical results.
A revision request authorizes only the stated revision inside the original scope.
New requirements that expand work/delivery scope need a new explicit decision.

Pause/resume/cancel_goal use a separate exact body `{schema_version:1,kind,goal_id}`:
goal_id required only for cancel_goal, otherwise null. Communication changes use
existing trusted preference interface separately; no hidden defaults broaden consent.
Reading, drafting and delivery consents remain separate. Silence never accepts work.

DecisionReceipt: `{schema_version:1,decision_id,action_id,commitment_id,
commitment_revision,outcome,responsibility_id,replayed}`; nullable IDs when not applicable;
outcome accepted/student_owned/declined/snoozed/revision_requested/paused/resumed/cancelled.
For a successful accept_private_work only, persist drafting/delivery consent, offer
consumption and exactly one new responsibility in one transaction. A successful
student_will_do/decline/snooze creates no responsibility; request_revision reuses the
existing authorized responsibility and creates only its bounded revision work.

For the same still-authorized owner, replay key and normalized body, return the original
receipt with replayed=true, even if offer expiry/control state has since changed; the
receipt reports history and never reauthorizes work or emits another token. This replay
lookup follows current actor/access checks but precedes the already-consumed/expiry
rejection. Same key with a changed normalized body returns controlled409/replay_conflict.

Once a decision consumes an offer/token, a DIFFERENT replay key with that token returns
controlled409/offer_consumed for both an identical decision and a different decision.
It creates no responsibility, consent, cancellation, schedule, revision or dispatch
authority and does not return another key's private receipt. In a race exactly one
transaction consumes the offer; the other receives offer_consumed. This does not block
pause/cancel controls, which have their own authenticated control messages without that
offer token. Snoozed/revised/materially changed work needs a newly issued current token.
Unconsumed stale/expired offers return409; nonowned offers generic404. Revoked actor
access cannot retrieve prior receipts. Controls/revisions are rechecked before later
steps, rendering and C4 dispatch, independently of this acceptance receipt.

## C6: private immutable checked files

Reuse the byte-stream sequence from [C6 architecture](AGENT-ACTIONS-v1.md#c6--checked-files-and-private-delivery):

```text
A reserve_render(lease, artifact_id, revision, format) -> RenderLease
M put_rendered_file(scope, render_id, descriptor, chunks) -> UploadAck
A finalize_render(lease, render_id, UploadAck) -> FileDescriptor
M open_owned_file(verified_actor, file_id) -> (FileDescriptor,chunks)
```

Descriptor exact keys: artifact_id,artifact_revision,renderer_version,format,mime,
filename,expected_byte_length,expected_sha256. UUID/revision current and owned;
format pdf/docx; byte_length1–10485760, lowercase64-hex SHA256; filename1–150 normalized
code points with no path separators, controls, NUL or dot-directory names, matching
format extension. MIME exact application/pdf or
application/vnd.openxmlformats-officedocument.wordprocessingml.document.
Chunks bytes<=65536; no path/URL/model storage key. Same render_id+descriptor+verified
bytes is idempotent; changed content conflicts. The private storage adapter counts
and hashes the actual stream, validates format, and durably acknowledges completed
upload before returning `{render_id,storage_handle,byte_length,sha256,durable:true}`.
An ETag is not SHA256. A lost upload acknowledgment reconciles that same render_id;
it never authorizes a message resend. Interrupted upload is provisional/private.

FileDescriptor exact keys: file_id,artifact_id,artifact_revision,renderer_version,
format,mime,filename,byte_length,sha256,check_report_id. A finalizes only after verifying
upload acknowledgment, current lease/consent/revision and the current check report
and sources. A stale upload can remain private historical bytes, never current
send-ready. No API accepts a model's ready=true assertion. C4 document payload must
match all finalized descriptor identities/checksum; bytes are revalidated by M on
read/provider upload. Private web downloads authenticate ownership every time and
stream with no-store and safe attachment filename. Cross-account misses share404.

Provider media ID is adapter-only metadata bound to exact file checksum, configured
account and actual provider validity. An expired media object can be re-uploaded
before dispatch with fresh authorization; unknown dispatch still forbids resend.
No stable public URL is created. Temporary provider-required bearer URLs, if needed,
require a separately reviewed lifetime/access design before implementation; they
are not silently introduced by this interface. Existing stored artifacts remain
private and versioned; this does not enact a new legal retention deadline.

## C7: model accounting, scheduling and operating limits

Proposed internal operations:

```text
reserve_model_call(lease, request_spec, price_revision, request_key) -> Reservation
mark_model_call_dispatched(reservation_id, attempt_token) -> DispatchReceipt
settle_model_call(verified_usage, reservation_id) -> Settlement
claim_due_agent(worker_id) -> SupervisorLease|null
record_agent_wait(lease, next_check_at, reason, coalescing_key) -> Receipt
set_operator_stop(verified_operator, enabled) -> StopReceipt
```

Reservation: `{schema_version:1,reservation_id,workflow_id,account_id,model,
price_revision,max_input_tokens,max_output_tokens,reserved_micro_usd,state}`.
IDs are server-derived; request_spec fixes bounded serialized input, tools and output
limit before reservation. Trusted price configuration supplies integer micro-USD
rates per million tokens, context limits and request overhead; reject unknown cost
upper bounds, unpriced model aliases or request changes after reservation. Round each
maximum UP: ceil(tokens*rate/1000000), including configured overhead. No float/credit
balance/model estimate is a hard cap. Future multimodal calls stay disabled until a
verified conservative price/token bound is defined; this does not narrow the vision.

Reserve under consistent ledger locks workflow→account→global; atomically check all
caps, outstanding reservations, per-workflow request count and dedup. Charge prompt,
tool, extraction/interpretation/review and retries, not only final reply. Persist
reservation and dispatch intent before provider IO. Settlement is keyed by immutable
provider call/reservation identity independently of task lease; expired/paused task
results cannot commit work, but incurred cost still settles. Known complete usage
records actual integer cost and releases unused reservation; timeout/partial/unknown
usage retains conservative liability until authoritative reconciliation. Duplicate
settlement idempotent, conflicting usage quarantined. Actual above reservation records
full liability, stops new calls and alerts operator; never hides the excess to fit a cap.
Refund/release-before-dispatch needs proof no request could have been sent; elapsed
time alone is insufficient. New retry requires a new reservation and attempt budget.

Defaults below are proposed bounded operating policy, NOT new spending authorization:

| Setting                                     | Initial value/behavior                                                                     |
| ------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Runtime and delivery activation             | off until explicit approved development run                                                |
| New account/workflow/global paid allowances | zero until configured by operator                                                          |
| Existing development usage                  | preserve prior$2 total ceiling and known/unknown reservations; no new calls here           |
| Episode model turns                         | 6, maximum20 under existing configuration                                                  |
| Output tokens/call                          | 2048 initial cap; actual model context/input bound from versioned configuration            |
| Active supervisor episodes                  | 1/student; no global shared lease serializing every student                                |
| Retry attempts                              | 3/workflow; each paid retry newly reserved                                                 |
| Pending task cap                            | 20/student under current setting; reject/hold additional work honestly                     |
| Worker lease                                | 300s initial; fenced renewal required, not authority after expiry                          |
| Proactive notices/offers                    | 3/student/local-calendar-day; atomically count reserved/unknown sends too                  |
| Requested replies/results                   | separate cap20/student/local-calendar-day; duplicate/unknown handling remains conservative |
| Quiet hours                                 | ask during onboarding; missing/ambiguous timezone or preference holds unsolicited dispatch |
| Future check horizon                        | 7days, coalesce duplicate event/revision/occurrence keys                                   |
| Worker readiness                            | missing required account/model/price/source configuration holds relevant work              |

Daily boundaries derive from a stored validated IANA timezone and actual calendar day,
including DST; a preference change cannot reset already consumed/reserved quota.
Reply/result caps do not imply an unsolicited consent exemption. STOP/pause ingestion
must remain available without buying a model call or sending a confirmation.
Use deterministic due-time/condition checks to schedule an episode; the model chooses
purpose and next steps from evidence, not a hardcoded daily task script. Idle/coalesced
unchanged scans do not buy inference. Earlier urgent evidence may advance a check;
source replay cannot create a duplicate job/notice. Browser refresh requests disclose
staleness rather than imagining new source data while the laptop is offline.

### Exact private health DTOs

These are authenticated projections, not public telemetry or extra model tools.
No source/message text, user/phone/provider identifiers, histories, exception strings
or credentials appear. An absent timestamp means unknown/not observed, not success.
All counts/micro-USD amounts are integers0..2^53-1, never bool/float/string. All known
timestamps are aware RFC3339 UTC strings. Unknown budget amounts are null, never a
fabricated zero; a known configured zero allowance remains integer0. Unknown amounts
hold paid work, not waive the cap. These projections cannot grant budget or readiness.

OperatorHealth has EXACT keys/types:

```text
{schema_version:1,operator_stop:bool,worker_heartbeats:[WorkerHeartbeat],
 oldest_due_at:timestamp|null,pending_count:int,held_count:int,
 unknown_dispatch_count:int,last_successful_sync_at:timestamp|null,
 last_delivered_at:timestamp|null,budget_remaining_micro_usd:int|null,
 budget_reserved_micro_usd:int|null}
```

worker_heartbeats is0–100 records, unique by(role,instance_id), sorted by that pair.
WorkerHeartbeat has EXACT keys/types:

```text
{role:"api"|"runtime"|"canvas_ingest"|"outlook_ingest"|"whatsapp_delivery"|"maintenance",
 instance_id:ASCII identifier1..100,last_seen_at:timestamp|null,ready:bool,
 state:"unknown"|"starting"|"ready"|"held"|"stopped"|"error"}
```

instance_id matches `[A-Za-z0-9._:-]{1,100}` and never contains an owner/recipient ID.
last_seen_at is a persisted server receipt time, not worker-supplied future success.
ready=true requires state=ready, a known fresh heartbeat and configuration/readiness
checks for that role; default freshness90s under trusted operator configuration.
Unknown/stale heartbeat cannot report ready; report unknown/ready=false unless an
explicit stopped state is recorded. A healthy API heartbeat is not Meta/Canvas/
WhatsApp acceptance, and Outlook's optional disabled role never means connected.

pending_count counts queued/runnable work; held_count counts explicitly held work;
unknown_dispatch_count counts unresolved outbound attempts, with no overlap assumptions.
oldest_due_at is the earliest unfinished persisted due time<=now, or null if none.
last_successful_sync_at is the last completed complete-coverage sync receipt;
last_delivered_at requires trusted matched delivered/read evidence. Both may be null.
Operator counts/times/budgets aggregate only the authenticated operator's authorized
development/service scope. budget_remaining is max(0, cap minus settled and outstanding
liability); the full deficit remains recorded in the ledger and blocks new calls, never
written off. budget_reserved is conservatively retained outstanding liability.
A failed ledger/configuration read yields unknown/null, not an optimistic cached balance.

StudentHealth is a SEPARATE exact projection for the verified student and selected
owned Canvas connection context; it is not a redacted operator object:

```text
{schema_version:1,paused:bool,service_state:"unknown"|"available"|"held"|"unavailable",
 connection_state:"unknown"|"pending_identity"|"connected"|"reconnect_required"|"disconnected",
 sync_state:"unknown"|"in_progress"|"partial"|"complete",
 last_successful_sync_at:timestamp|null,last_delivered_at:timestamp|null,
 next_check_at:timestamp|null,pending_count:int,held_count:int,
 budget_remaining_micro_usd:int|null,budget_reserved_micro_usd:int|null}
```

Counts and budgets are ONLY that student's owned work/allowance/liabilities; they
never disclose another student's activity, global caps, server instance names,
worker topology or operator health/balances. Sync state/time comes from the selected
owned connection; last_delivered_at is only the linked student's matched receipts.
next_check_at is a persisted authorized student check, null if unknown/not scheduled.
service_state=available requires required worker/configuration readiness and no applicable
stop; a configured account alone is insufficient. Student pause or operator stop makes
applicable work held, without pretending to recall in-flight activity. Authorization
failure returns the existing generic auth/not-found response, never this DTO for another
student. UI labels/HTTP routing remain M's implementation after exact agreement.

## Migrations, activation and rollback order

No numbered migration is allocated by this proposal. Current local branch has001–007,
009–013 at this proposal's original base; later A storage work reserves014/015.
008 belongs to parked A4. Last recorded isolated deployment has001–007+009.
Read exact integration/deployment ledgers before reserving the next unused number;
do not modify or reuse an applied file, or assume all reviewed branches are deployed.

After M agreement, implement additive scoped slices: (1) immutable operation/budget
and offer-token/decision tables plus replay keys/fences; (2) extend existing outbox
with nullable capability/file/revision references, preserving legacy text behavior;
(3) private render/file records and adapter capability negotiation; (4) due-check,
health and operator-stop composition. Keep old columns/consumers and feature defaults
until each replacement has reviewed consumers; no second queue/store/runtime.
Document-upload schema2 #118 remains a distinct dependency and review gate.

Before any bounded activation, operator verifies exact code/ledger/migrations, isolated
accounts, consent, Meta pricing and all budgets including prior unknown reservations,
source readiness, current template/media capabilities and stop/recovery procedures.
Synthetic acceptance includes cross-account/button/file denial, changed evidence after
acceptance, pause/unlink during work, unknown send, upload mismatch, ledger races and
late settlement, DST quotas and crash recovery. Live delivered/checked results need
separate consenting evidence within the already approved run; this proposal grants none.

Rollback: persist operator stop, stop new claims/dispatch, leave inbound STOP/control
processing available, drain/fence active leases and record uncertain in-flight costs/
sends, then roll back executable consumers only if additive schema remains compatible.
Do not down-migrate away receipts, consent history, reservations or private references.
Never requeue unknown sends or zero unknown liabilities. Reconcile before any restart;
only explicit approved configuration reactivates. Full provider/UI/worker reliability
remains P2–P6 work, not a P0 paper pass.

## Review decisions and example cases

[Fixtures](../../tests/fixtures/agent_operations_v1.json) are synthetic review examples,
not executable validators or authorization grants. M must agree C4 payload capability
mapping/provider statuses, C5 verified inbound/token handling, C6 streaming/storage
acknowledgment, C7 accounting/health and migration/stop topology. Record exact commit
agreement or precise changes before consumer work. A owns validators/storage/runtime;
M owns channel/app/web/provider/file IO/deployment. Neither edits the other's claimed
files. Interface agreement alone does not close live delivery/access gates.
