# One-course proactive delivery v1 — implementation candidate

Owner A shared/contracts; M HTTP/transport assembly. Extends the ORIGINAL
whatsapp_outbound/claim/authorization/result/signed-receipt queue; no parallel sender.
Migration024 not deployed. Old reply authorization remains unchanged.

## Exact new calls

- set_course_notification_consent(verified_user, supervision_id, consent=bool):
  session-owned proactive opt-in, defaultfalse. Existing reply consent alone is
  insufficient. Revoke remains possible after disconnect.
- enqueue_course_offer(verified_user, supervision_id, offer_id) -> {id,state}:
  trusted assembly; no content or recipient arguments. Reads saved offer, rechecks
  consent/current source pins/scope and captures current linked recipient/generation.
  Exactly one queue row per offer, including unknown outcomes. No blind requeue.
- Existing claim_whatsapp_delivery returns DeliveryClaim.task_id=None and offer_id
  for proactive offers. Replies retain task_id and offer_id=None. This is an internal
  discriminator, not a user/model-supplied ID. Typed SQL XOR/FK enforces ownership.
- Existing authorize_whatsapp_send accepts new approved_offer_templates=() and
  offer_template_key=None. Existing supports_templates=False default is preserved.
  M passes trusted Settings.whatsapp_approved_offer_templates and
  whatsapp_offer_template_key after explicitly enabling adapter template support.
  ApprovedOfferTemplate/OfferTemplateParameter use offer_text; reply-only templates
  are rejected for offers. Actual Meta approval/account match must be configured,
  not inferred from type validation or code tests.
- Existing record_whatsapp_result and signed record_whatsapp_status reconcile offer
  sends too. No new receipt implementation. Accepted is not delivered.

## Dispatch checks and crash semantics

Existing agent/outbound claim fence also binds optional offer identity. Authorization
rechecks agent/monitor pause, explicit proactive consent, offer pending state/24h
expiry, course connection generation/scope, all pinned current sources with act
freshness, original message, current link/recipient, global communication consent,
quiet hours, channel window and approved account-scoped offer template when needed.
At most3proactive authorizations/student/rolling24h, including unknown dispatches.
Account configuration/recipient/template selection never come from the model.

Authorization atomically records dispatch_at/account/payload in the original outbox
before returning permitted. Reauthorization of an already consumed claim fails. Lost
response, exception, abandoned send or persistence failure preserves unknown; no retry
of a possibly dispatched action. Queued/deferred failures before authorization may
be held and rechecked. Source/control changes cancel or hold, never return stale text.
Model decisions cannot grant notification consent, template approval or delivery scope.

M keeps no-store/session auth, maps signed linked inbound decisions to A's existing
acceptance API and dispatches only the returned typed payload. Never call adapter.send
with claim.content directly. Wire approved reply and proactive templates separately.
No live provider call, verified business, template approval, deployment or spend is
implied. Test phone receipt and signed delivered callback remain actual live gates.
