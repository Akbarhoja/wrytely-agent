"""Internal storage/worker contract. Signed callback parsing belongs to integrations."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from contracts.templates import TemplatePayload, TextPayload


@dataclass(frozen=True)
class DeliveryClaim:
    action_id: UUID
    agent_id: UUID
    task_id: UUID
    recipient: str
    content: str
    link_generation: UUID | None
    worker_id: str
    attempt_token: UUID
    deadline: datetime


@dataclass(frozen=True)
class SendAuthorization:
    state: Literal["permitted", "held", "cancelled"]
    reason: str | None = None
    retry_at: datetime | None = None
    recipient: str | None = None
    text: str | None = None
    payload: TextPayload | TemplatePayload | None = None


class WhatsAppStatusEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    business_id: str = Field(min_length=1, max_length=100)
    phone_number_id: str = Field(min_length=1, max_length=100)
    provider_ref: str = Field(min_length=1, max_length=512)
    recipient: str = Field(pattern=r"^[0-9]{7,15}$")
    status: Literal["sent", "delivered", "read", "failed"]
    event_at: AwareDatetime
