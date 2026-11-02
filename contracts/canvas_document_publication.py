"""Exact agreed document-only C2 publication shape; no mixed inline schema2."""

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from contracts.canvas_sync import DiscoveryBatch, Strict, course_id

PAIRS = {
    "assignments": "assignment",
    "syllabus": "syllabus",
    "pages": "page",
    "files": "file",
    "announcements": "announcement",
    "discussions": "discussion",
    "submissions": "submission",
    "grades": "grade",
}


def document_kind_allowed(resource, kind):
    return kind == PAIRS.get(resource) or (resource == "discussions" and kind == "entry")


class DocumentResource(Strict):
    course_id: str
    kind: Literal[
        "assignments",
        "syllabus",
        "pages",
        "files",
        "announcements",
        "discussions",
        "submissions",
        "grades",
    ]

    @field_validator("course_id")
    @classmethod
    def valid_course(cls, value):
        return course_id(value)


class DocumentItem(Strict):
    kind: Literal[
        "assignment",
        "syllabus",
        "page",
        "file",
        "announcement",
        "discussion",
        "submission",
        "grade",
        "entry",
    ]
    provider_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    provider_updated_at: str | None
    title: str = Field(max_length=300)
    reference: str = Field(min_length=1, max_length=2000)
    upload_id: str

    @field_validator("provider_updated_at")
    @classmethod
    def valid_update(cls, value):
        if value is not None:
            DiscoveryBatch.aware_timestamp(value)
        return value

    @field_validator("upload_id")
    @classmethod
    def valid_uuid(cls, value):
        if str(UUID(value)) != value:
            raise ValueError("Canonical upload UUID required")
        return value


class DocumentBatch(DiscoveryBatch):
    schema_version: Literal[2]
    batch_type: Literal["canvas_documents"]
    resource: DocumentResource
    items: list[DocumentItem] = Field(max_length=50)

    @model_validator(mode="after")
    def document_kinds(self):
        if any(not document_kind_allowed(self.resource.kind, item.kind) for item in self.items):
            raise ValueError("Document kind/resource mismatch")
        if len({item.upload_id for item in self.items}) != len(self.items):
            raise ValueError("Duplicate document upload")
        return self
