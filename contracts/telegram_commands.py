"""Explicit academic commands from authenticated private Telegram text only."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TelegramAcademicCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["accept_offer", "decline_offer", "revise_artifact", "send_artifact"]
    target_id: UUID
    instructions: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def coherent(self):
        if self.kind == "revise_artifact":
            if not self.instructions.strip():
                raise ValueError("Explicit revision instructions required")
        elif self.instructions:
            raise ValueError("Only revision accepts instructions")
        return self


def parse_academic_command(text):
    """No implicit/latest targets, reply-context guessing or model interpretation."""
    if not isinstance(text, str) or len(text) > 12000:
        raise ValueError("Invalid command")
    parts = text.split(maxsplit=2)
    if not parts or parts[0] not in {"/accept", "/decline", "/revise", "/file"}:
        return None
    if len(parts) < 2:
        raise ValueError("Explicit command target required")
    try:
        target = UUID(parts[1])
    except ValueError:
        raise ValueError("Invalid command target") from None
    if str(target) != parts[1].lower():
        raise ValueError("Canonical command target required")
    instructions = parts[2].strip() if len(parts) == 3 else ""
    if (parts[0] == "/revise" and not instructions) or (parts[0] != "/revise" and instructions):
        raise ValueError("Invalid command instructions")
    return TelegramAcademicCommand(
        kind={
            "/accept": "accept_offer",
            "/decline": "decline_offer",
            "/revise": "revise_artifact",
            "/file": "send_artifact",
        }[parts[0]],
        target_id=target,
        instructions=instructions,
    )
