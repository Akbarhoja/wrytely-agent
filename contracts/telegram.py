"""Trusted Telegram envelopes; usernames and model output never establish identity."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contracts.templates import ArtifactPayload


def positive_id(value):
    if type(value) is not int or not 0 < value < 2**52:
        raise ValueError("Invalid Telegram identity")
    return value


@dataclass(frozen=True)
class TelegramText:
    update_id: int
    message_id: int
    chat_id: int
    text: str
    event_at: datetime


@dataclass(frozen=True)
class TelegramClaim:
    action_id: UUID
    bot_id: int
    chat_id: int
    generation: UUID
    attempt_token: UUID
    user_id: str
    kind: str
    content: str
    artifact_file_id: UUID | None = None


@dataclass(frozen=True)
class TelegramPermit:
    state: str
    reason: str | None = None
    content: str | None = None
    payload: ArtifactPayload | None = None
