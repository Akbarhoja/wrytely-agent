"""Internal draft/assessment types; a model never sets artifact readiness directly."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(StrictModel):
    version_id: UUID
    claim: str = Field(min_length=1, max_length=2000)
    quote: str = Field(min_length=1, max_length=2000)

    @field_validator("claim", "quote")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Evidence must contain text")
        return value


class DraftArtifact(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=24000)
    citations: list[Citation] = Field(max_length=30)
    disclosure: str = Field(max_length=2000)

    @field_validator("body", "title")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Draft must contain text")
        return value


class Assessment(StrictModel):
    claim_support: list[Literal["supported", "unsupported", "uncertain"]] = Field(max_length=30)
    rubric_coverage: list[Literal["covered", "missing", "uncertain"]] = Field(max_length=30)
    policy_allows_drafting: bool
    disclosure_satisfied: bool
    rubric_complete: bool
    uncited_claims: bool
    reason: str = Field(min_length=1, max_length=3000)


class CoursePolicy(StrictModel):
    """Explicit source evidence, supplied by trusted assembly, not a student override."""

    status: Literal["permitted", "disclosure_required", "limited", "prohibited", "unknown"]
    version_id: UUID
    quote: str = Field(min_length=1, max_length=2000)


class RubricItem(StrictModel):
    version_id: UUID
    quote: str = Field(min_length=1, max_length=2000)
