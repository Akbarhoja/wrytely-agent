"""Validated discovery-only C2 envelope; provider IO and academic ingestion are separate."""

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from contracts.source_digest import canonical_source_bytes

RESOURCE_KINDS = frozenset(
    {
        "syllabus",
        "assignments",
        "announcements",
        "discussions",
        "modules",
        "pages",
        "files",
        "submissions",
        "grades",
    }
)
REASONS = frozenset(
    {
        "more_pages",
        "login_required",
        "permission_denied",
        "initial_post_required",
        "rate_limited",
        "provider_unavailable",
        "extraction_failed",
        "size_limit",
        "cursor_invalid",
        "unsupported_format",
    }
)


def replay_key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value):
        raise ValueError("Invalid replay key")
    return value


def course_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", value):
        raise ValueError("Invalid course ID")
    return value


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Resource(Strict):
    course_id: None = None
    kind: Literal["courses"]


class Coverage(Strict):
    state: Literal["complete", "partial", "restricted", "unsupported"]
    reason: str | None
    seen_count: int = Field(ge=0, le=5000)

    @model_validator(mode="after")
    def controlled_reason(self):
        if (self.state == "complete" and self.reason is not None) or (
            self.state != "complete" and self.reason not in REASONS
        ):
            raise ValueError("Invalid coverage reason")
        return self


class Course(Strict):
    provider_id: str
    provider_updated_at: str | None
    title: str = Field(max_length=500)
    reference: str = Field(max_length=2048)
    fields: dict
    content: Literal[""]
    coverage: Literal["complete", "partial", "restricted", "unsupported"]
    missing: list[str] = Field(max_length=50)

    @field_validator("provider_id")
    @classmethod
    def valid_id(cls, value):
        return course_id(value)

    @model_validator(mode="after")
    def metadata_only(self):
        if self.fields.keys() != {"course_code", "timezone", "enrollment_state"}:
            raise ValueError("Exact course metadata fields required")
        if any(
            v is not None and (not isinstance(v, str) or len(v) > 500) for v in self.fields.values()
        ):
            raise ValueError("Invalid course metadata")
        if self.coverage == "complete" and self.missing:
            raise ValueError("Complete metadata cannot have missing fields")
        canonical_source_bytes(self.digest_payload())
        return self

    def digest_payload(self):
        return {
            "digest_version": 1,
            "kind": "course",
            "title": self.title,
            "content": self.content,
            "fields": self.fields,
            "coverage": self.coverage,
            "missing": self.missing,
        }


class DiscoveryBatch(Strict):
    schema_version: Literal[1]
    connection_id: str
    generation: int = Field(ge=1)
    scan_id: str
    batch_key: str
    subject: str = Field(min_length=1, max_length=1024)
    resource: Resource
    observed_at: str
    items: list[Course] = Field(max_length=50)
    coverage: Coverage
    next_cursor: str | None = Field(max_length=4000)

    @field_validator("schema_version", mode="before")
    @classmethod
    def exact_schema_integer(cls, value):
        if type(value) is not int:
            raise ValueError("Integer schema version required")
        return value

    @field_validator("batch_key")
    @classmethod
    def valid_key(cls, value):
        return replay_key(value)

    @field_validator("connection_id", "scan_id")
    @classmethod
    def valid_uuid(cls, value):
        UUID(value)
        return value

    @field_validator("observed_at")
    @classmethod
    def aware_timestamp(cls, value):
        if not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
            r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])",
            value,
        ):
            raise ValueError("Aware RFC3339 observation required")
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value

    @model_validator(mode="after")
    def page_integrity(self):
        if len({item.provider_id for item in self.items}) != len(self.items):
            raise ValueError("Duplicate course in page")
        if self.next_cursor is not None and (
            not self.next_cursor
            or self.coverage.state != "partial"
            or self.coverage.reason != "more_pages"
        ):
            raise ValueError("Cursor requires more_pages coverage")
        return self


class Checkpoint(Strict):
    resource: Literal["courses"]
    next_cursor: str | None = Field(max_length=4000)
    sequence: int = Field(ge=0, le=100)
    scope_revision: int = Field(ge=0)
