"""One delivery attempt using the existing durable Store; no independent retry queue."""

from contracts.models import DeliveryResult
from integrations.whatsapp import WhatsAppAdapter
from shared.db import LeaseLost, Store


def run_once(
    store: Store,
    adapter: WhatsAppAdapter,
    *,
    worker_id: str,
    business_id: str,
    phone_number_id: str,
) -> str:
    claim = store.claim_whatsapp_delivery(worker_id)
    if claim is None:
        return "idle"
    try:
        authorization = store.authorize_whatsapp_send(
            claim, business_id=business_id, phone_number_id=phone_number_id
        )
    except LeaseLost:
        return "lease_lost"
    if authorization.state != "permitted":
        return authorization.state
    # Authorization is consumed once. Never cache it or reuse it on restart.
    # Control changes after this decision cannot recall an in-flight request.
    try:
        result = adapter.send(
            recipient=authorization.recipient,
            text=authorization.text,
            action_id=claim.action_id,
        )
    except Exception:
        # Even an unexpected transport exception may conceal a dispatched request.
        result = DeliveryResult(internal_id=claim.action_id, state="unknown")
    # Do not swallow persistence failure or lease expiry: the stored sending state
    # is recovered as unknown. Neither failure permits another dispatch.
    store.record_whatsapp_result(claim, result)
    return result.state
