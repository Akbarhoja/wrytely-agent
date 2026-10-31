"""C2 extracted-content validation, not a parser, provider client or permission grant."""

import json
import re
import unicodedata
from copy import deepcopy
from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from contracts.canvas_sync import DiscoveryBatch, Strict, course_id
from contracts.source_digest import canonical_source_bytes

RESOURCE_TYPES = {
    "assignments": {"assignment"},
    "syllabus": {"syllabus"},
    "pages": {"page"},
    "announcements": {"announcement"},
    "discussions": {"discussion", "entry"},
    "submissions": {"submission"},
    "grades": {"grade"},
}
FIELDS = {
    "assignment": {
        "due_at",
        "unlock_at",
        "lock_at",
        "points_possible",
        "submission_types",
        "rubric",
        "published",
    },
    "syllabus": {"page_id", "module_ids", "source_format"},
    "page": {"page_id", "module_ids", "source_format"},
    "announcement": {"author_role", "posted_at", "announcement_id"},
    "discussion": {"topic_id", "parent_entry_id", "author_role", "required_initial_post", "due_at"},
    "entry": {"topic_id", "parent_entry_id", "author_role", "required_initial_post", "due_at"},
    "submission": {"assignment_id", "submitted_at", "workflow_state", "attempt", "late", "missing"},
    "grade": {"assignment_id", "score", "points_possible", "grading_type", "grade", "grade_basis"},
}


def _decimal(value):
    if value is not None and (
        not isinstance(value, str)
        or len(value) > 64
        or not re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value)
    ):
        raise ValueError("Decimal string required")
    if value is None:
        return None
    whole, separator, fraction = value.partition(".")
    fraction = fraction.rstrip("0")
    result = whole + ("." + fraction if separator and fraction else "")
    return "0" if result == "-0" else result


def _rubric(rows, *, ratings=False):
    if rows is None:
        return
    if not isinstance(rows, list) or len(rows) > (50 if ratings else 100):
        raise ValueError("Rubric limit")
    required = {"id", "description", "points"} | (set() if ratings else {"ratings"})
    allowed = (
        required
        | {"long_description"}
        | (
            set()
            if ratings
            else {"criterion_use_range", "ignore_for_scoring", "learning_outcome_id", "vendor_guid"}
        )
    )
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not required <= row.keys() or not row.keys() <= allowed:
            raise ValueError("Invalid rubric fields")
        key = row["id"]
        if not isinstance(key, str) or not 1 <= len(key) <= 256:
            raise ValueError("Invalid rubric ID")
        key = unicodedata.normalize("NFC", key.replace("\r\n", "\n").replace("\r", "\n"))
        if key in seen:
            raise ValueError("Duplicate normalized rubric ID")
        seen.add(key)
        for name, limit in (
            ("description", 4000),
            ("long_description", 12000),
            ("learning_outcome_id", 256),
            ("vendor_guid", 256),
        ):
            value = row.get(name)
            if value is not None and (not isinstance(value, str) or len(value) > limit):
                raise ValueError("Invalid rubric text")
        for name in ("criterion_use_range", "ignore_for_scoring"):
            if row.get(name) is not None and type(row[name]) is not bool:
                raise ValueError("Invalid rubric flag")
        row["points"] = _decimal(row["points"])
        if not ratings:
            _rubric(row["ratings"], ratings=True)


class AcademicResource(Strict):
    course_id: str
    kind: Literal[
        "assignments", "syllabus", "pages", "announcements", "discussions", "submissions", "grades"
    ]

    @field_validator("course_id")
    @classmethod
    def valid_course(cls, value):
        return course_id(value)


class EvidenceItem(Strict):
    kind: (
        Literal[
            "assignment",
            "syllabus",
            "page",
            "announcement",
            "discussion",
            "entry",
            "submission",
            "grade",
        ]
        | None
    ) = None
    provider_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    provider_updated_at: str | None
    title: str = Field(max_length=300)
    reference: str = Field(min_length=1, max_length=2000)
    fields: dict
    content: str = Field(max_length=24000)
    coverage: Literal["complete", "partial", "restricted", "unsupported"]
    missing: list[str] = Field(max_length=50)

    @field_validator("provider_updated_at")
    @classmethod
    def aware_update(cls, value):
        if value is not None:
            DiscoveryBatch.aware_timestamp(value)
        return value

    def payload(self, kind):
        if self.fields.keys() != FIELDS[kind]:
            raise ValueError("Exact resource fields required")
        fields = deepcopy(self.fields)
        for name, value in fields.items():
            if name in {"points_possible", "score"}:
                fields[name] = _decimal(value)
            elif name == "rubric":
                _rubric(value)
            elif name in {"published", "late", "missing", "required_initial_post"}:
                if value is not None and type(value) is not bool:
                    raise ValueError("Boolean field required")
            elif name == "attempt":
                if value is not None and (type(value) is not int or not 0 <= value <= 1000000):
                    raise ValueError("Invalid attempt")
            elif name in {"submission_types", "module_ids"}:
                if value is not None and (
                    not isinstance(value, list)
                    or len(value) > 1000
                    or any(not isinstance(v, str) or not 1 <= len(v) <= 128 for v in value)
                    or value != sorted(set(value))
                ):
                    raise ValueError("Sorted unique field list required")
            elif value is not None and (not isinstance(value, str) or len(value) > 1024):
                raise ValueError("Invalid resource field")
            if (
                name in {"posted_at", "due_at", "unlock_at", "lock_at", "submitted_at"}
                and value is not None
            ):
                DiscoveryBatch.aware_timestamp(value)
                if name == "posted_at":
                    fields[name] = (
                        datetime.fromisoformat(value.replace("Z", "+00:00"))
                        .astimezone(UTC)
                        .isoformat(timespec="microseconds")
                        .replace("+00:00", "Z")
                    )
        if any(not re.fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,127}", m) for m in self.missing):
            raise ValueError("Invalid missing reason")
        if self.coverage == "complete" and (
            self.missing or not self.content.strip() or not self.title.strip()
        ):
            raise ValueError("Complete evidence requires nonblank text/title and no gaps")
        return json.loads(
            canonical_source_bytes(
                {
                    "digest_version": 1,
                    "kind": kind,
                    "title": self.title,
                    "content": self.content,
                    "fields": fields,
                    "coverage": self.coverage,
                    "missing": self.missing,
                }
            )
        )


class AcademicBatch(DiscoveryBatch):
    resource: AcademicResource
    items: list[EvidenceItem] = Field(max_length=50)

    @model_validator(mode="after")
    def page_integrity(self):
        kinds = RESOURCE_TYPES[self.resource.kind]
        seen = set()
        for item in self.items:
            kind = item.kind or (
                "discussion" if self.resource.kind == "discussions" else next(iter(kinds))
            )
            if kind not in kinds or (kind, item.provider_id) in seen:
                raise ValueError("Duplicate or mismatched evidence kind")
            seen.add((kind, item.provider_id))
            item.payload(kind)
        if self.next_cursor is not None and (
            not self.next_cursor
            or self.coverage.state != "partial"
            or self.coverage.reason != "more_pages"
        ):
            raise ValueError("Cursor requires more_pages coverage")
        return self
