from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


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


class PlannerDecision(BaseModel):
    """One bounded internal step, or an honest terminal/waiting reason."""

    model_config = ConfigDict(extra="forbid")
    action: Literal["work", "blocked", "done"]
    reason: str = Field(min_length=1, max_length=2000)
    step_key: str = Field(min_length=1, max_length=100)
    instruction: str = Field(max_length=4000)

    @field_validator("reason", "step_key")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Must contain text")
        return value.strip()


class DraftPlannerDecision(PlannerDecision):
    """Only offered when a trusted private-draft intent exists."""

    action: Literal["work", "draft", "blocked", "done"]


class SourceObservation(BaseModel):
    """Draft internal connector contract; ownership is supplied by trusted assembly."""

    model_config = ConfigDict(extra="forbid")
    source_key: str = Field(min_length=1, max_length=256)
    external_revision: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=300)
    reference: str = Field(min_length=1, max_length=2000)
    coverage: Literal["snapshot", "api", "feed", "group"]
    content: str = Field(min_length=1, max_length=24000)
    retrieved_at: AwareDatetime

    @field_validator("source_key", "external_revision", "title", "reference", "content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Must contain text")
        return value
