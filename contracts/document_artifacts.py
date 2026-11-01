"""Internal v2 evidence types. Existing public legacy artifact DTOs are unchanged."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from contracts.artifacts import StrictModel
from shared.document_citations import _citation


class LegacyEvidence(StrictModel):
    kind: Literal["legacy"]
    version_id: UUID
    quote: str = Field(min_length=1, max_length=2000, strict=True)

    @field_validator("quote")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Nonblank quote required")
        return value


class DocumentEvidence(StrictModel):
    kind: Literal["canvas_document"]
    object_id: UUID
    observation_id: UUID
    document_version_id: UUID
    segment_id: UUID
    slot: int = Field(ge=0, le=511, strict=True)
    page: int | None = Field(ge=1, le=200, strict=True)
    start: int = Field(ge=0, le=200000, strict=True)
    end: int = Field(ge=1, le=200000, strict=True)
    quote: str = Field(min_length=1, max_length=4000, strict=True)

    @model_validator(mode="after")
    def exact_reference(self):
        _citation(self.model_dump(exclude={"kind"}))
        return self


Evidence = Annotated[LegacyEvidence | DocumentEvidence, Field(discriminator="kind")]


class EvidenceClaim(StrictModel):
    claim: str = Field(min_length=1, max_length=2000)
    evidence: Evidence

    @field_validator("claim")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Nonblank claim required")
        return value


class DraftArtifactV2(StrictModel):
    schema_version: Literal[2]
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=24000)
    citations: list[EvidenceClaim] = Field(max_length=30)
    disclosure: str = Field(max_length=2000)

    @field_validator("title", "body")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Nonblank draft required")
        return value


class CoursePolicyV2(StrictModel):
    status: Literal["permitted", "disclosure_required", "limited", "prohibited", "unknown"]
    evidence: Evidence

    @property
    def quote(self):
        return self.evidence.quote


class RubricItemV2(StrictModel):
    evidence: Evidence

    @property
    def quote(self):
        return self.evidence.quote


class RequirementAssessmentV2(StrictModel):
    policy: CoursePolicyV2 | None
    rubric: list[RubricItemV2] = Field(max_length=30)
    reason: str = Field(min_length=1, max_length=2000)
