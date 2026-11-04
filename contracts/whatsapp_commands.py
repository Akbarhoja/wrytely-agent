"""Post-signature structured command, not an HTTP body or model tool contract."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class WhatsAppCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["accept_offer", "decline_offer", "revise_artifact", "send_artifact"]
    target_id: UUID | None = None
    instructions: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def coherent(self):
        if self.kind == "revise_artifact":
            if not self.instructions.strip():
                raise ValueError("Explicit revision instructions required")
        elif self.instructions:
            raise ValueError("Only revision accepts instructions")
        return self


class WhatsAppCommandEnvelope(BaseModel):
    """All identity/context fields must come from authenticated provider data."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    provider_id: str = Field(min_length=1, max_length=512)
    sender: str = Field(pattern=r"^[0-9]{7,15}$")
    event_at: AwareDatetime
    business_id: str = Field(min_length=1, max_length=100)
    phone_number_id: str = Field(min_length=1, max_length=100)
    reply_to_provider_ref: str | None = Field(default=None, min_length=1, max_length=512)
    command: WhatsAppCommand

    @model_validator(mode="after")
    def target_context(self):
        if self.command.target_id is None and self.reply_to_provider_ref is None:
            raise ValueError("Explicit target or authenticated reply context required")
        return self
