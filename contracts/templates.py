"""Trusted template configuration, not model inputs or proof of provider approval."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TemplateParameter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    source: Literal["literal", "reply_text"]
    literal: str | None = Field(default=None, max_length=1024)
    max_length: int = Field(default=1024, ge=1, le=1024)

    @model_validator(mode="after")
    def valid_source(self):
        if self.source == "literal":
            if (
                self.literal is None
                or not self.literal.strip()
                or len(self.literal) > self.max_length
            ):
                raise ValueError("Literal parameter must fit configured limit")
        elif self.literal is not None:
            raise ValueError("Reply text cannot supply a literal")
        return self


class ApprovedTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str = Field(pattern=r"^[a-z0-9_]{1,100}$")
    name: str = Field(pattern=r"^[a-z0-9_]{1,512}$")
    language: str = Field(pattern=r"^[a-z]{2,3}(?:_[A-Z]{2})?$")
    business_id: str = Field(min_length=1, max_length=100)
    phone_number_id: str = Field(min_length=1, max_length=100)
    provider_approved: Literal[True]
    body_parameters: tuple[TemplateParameter, ...] = Field(min_length=1, max_length=10)

    @field_validator("provider_approved", mode="before")
    @classmethod
    def explicit_approval(cls, value):
        if value is not True:
            raise ValueError("Provider approval must be explicitly true")
        return value

    @model_validator(mode="after")
    def carries_reply(self):
        if sum(p.source == "reply_text" for p in self.body_parameters) != 1:
            raise ValueError("Reply template must carry the full reply exactly once")
        return self


class TextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["text"] = "text"
    text: str = Field(min_length=1, max_length=4096)


class TemplatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["template"] = "template"
    key: str
    name: str
    language: str
    body_parameters: tuple[str, ...]
