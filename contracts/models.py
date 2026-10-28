from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


@dataclass(frozen=True)
class Identity:
    user_id: str
    session_id: str


class MessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=12000)

    @field_validator("content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must contain text")
        return value.strip()


class AgentControl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paused: bool


@dataclass(frozen=True)
class TaskLease:
    task_id: UUID
    agent_id: UUID
    user_id: str
    lease_token: UUID
    attempt: int
    message_id: UUID


@dataclass(frozen=True)
class ModelTurn:
    output: list[dict[str, Any]]
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class ModelClient(Protocol):
    def turn(self, history: list[dict], tools: list[dict]) -> ModelTurn: ...


class SessionVerifier(Protocol):
    def verify(self, token: str) -> Identity: ...


class DeliveryResult(BaseModel):
    """Receipt evidence, never an assertion of delivery from a send attempt alone."""

    model_config = ConfigDict(extra="forbid")
    state: Literal["queued", "deferred", "accepted", "delivered", "unknown", "failed"]
    internal_id: UUID
    provider_ref: str | None = None
    retry_at: str | None = None


class ChannelAdapter(Protocol):
    """Provider implementations must document ambiguous-send reconciliation limits."""

    def send(self, *, recipient: str, text: str, action_id: UUID) -> DeliveryResult: ...
