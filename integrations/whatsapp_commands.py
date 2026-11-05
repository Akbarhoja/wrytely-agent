"""Bounded explicit slash commands, only after raw signature/account validation."""

from uuid import UUID

from contracts.whatsapp_commands import WhatsAppCommand, WhatsAppCommandEnvelope
from integrations.whatsapp import WhatsAppText


class InvalidWhatsAppCommand(ValueError):
    """Recognized command namespace: acknowledge safely, never infer a chat task."""


def parse_command(message: WhatsAppText, *, business_id: str, phone_number_id: str):
    text = message.text.strip()
    if not text.startswith("/"):
        return None
    if len(text) > 4096:
        raise InvalidWhatsAppCommand()
    pieces = text.split(maxsplit=1)
    kinds = {
        "/accept": "accept_offer",
        "/decline": "decline_offer",
        "/revise": "revise_artifact",
        "/file": "send_artifact",
    }
    kind = kinds.get(pieces[0].casefold())
    if kind is None or message.event_at is None:
        raise InvalidWhatsAppCommand()
    tail = pieces[1].strip() if len(pieces) == 2 else ""
    target, instructions = None, ""
    try:
        if kind == "revise_artifact":
            args = tail.split(maxsplit=1)
            if not args:
                raise ValueError()
            try:
                target = UUID(args[0])
            except ValueError:
                instructions = tail
            else:
                instructions = args[1].strip() if len(args) == 2 else ""
        elif tail:
            target = UUID(tail)
        return WhatsAppCommandEnvelope(
            provider_id=message.provider_id,
            sender=message.sender,
            event_at=message.event_at,
            business_id=business_id,
            phone_number_id=phone_number_id,
            reply_to_provider_ref=message.reply_to_provider_ref,
            command=WhatsAppCommand(kind=kind, target_id=target, instructions=instructions),
        )
    except ValueError:
        raise InvalidWhatsAppCommand() from None
