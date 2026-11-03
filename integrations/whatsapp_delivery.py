"""One delivery attempt using the existing durable Store; no independent retry queue."""

from contracts.models import DeliveryResult
from contracts.templates import TemplatePayload, TextPayload
from integrations.whatsapp import WhatsAppAdapter
from shared.db import LeaseLost, Store


def run_once(
    store: Store,
    adapter: WhatsAppAdapter,
    *,
    worker_id: str,
    business_id: str,
    phone_number_id: str,
    approved_templates=(),
    reply_template_key=None,
    approved_offer_templates=(),
    offer_template_key=None,
) -> str:
    claim = store.claim_whatsapp_delivery(worker_id)
    if claim is None:
        return "idle"
    try:
        authorization = store.authorize_whatsapp_send(
            claim,
            business_id=business_id,
            phone_number_id=phone_number_id,
            supports_templates=True,
            approved_templates=approved_templates,
            reply_template_key=reply_template_key,
            approved_offer_templates=approved_offer_templates,
            offer_template_key=offer_template_key,
        )
    except LeaseLost:
        return "lease_lost"
    if authorization.state != "permitted":
        return authorization.state
    # Authorization is consumed once. Never cache it or reuse it on restart.
    # Control changes after this decision cannot recall an in-flight request.
    try:
        payload = authorization.payload
        if isinstance(payload, TextPayload):
            result = adapter.send(
                recipient=authorization.recipient,
                text=payload.text,
                action_id=claim.action_id,
            )
        elif isinstance(payload, TemplatePayload):
            result = adapter.send_template(
                recipient=authorization.recipient,
                name=payload.name,
                language=payload.language,
                body_parameters=payload.body_parameters,
                action_id=claim.action_id,
            )
        else:
            raise ValueError("Missing authoritative delivery payload")
    except Exception:
        # Even an unexpected transport exception may conceal a dispatched request.
        result = DeliveryResult(internal_id=claim.action_id, state="unknown")
    # Do not swallow persistence failure or lease expiry: the stored sending state
    # is recovered as unknown. Neither failure permits another dispatch.
    store.record_whatsapp_result(claim, result)
    return result.state
