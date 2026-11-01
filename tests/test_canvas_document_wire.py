"""Synthetic root validation only; no Canvas access or upload acceptance."""

import hashlib
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from shared.canvas_document_wire import validate_canvas_document

VECTORS = json.loads((Path(__file__).parent / "fixtures/canvas_document_v2.json").read_text())[
    "vectors"
]


def arguments(vector=None):
    vector = deepcopy(vector or VECTORS[0])
    payload = vector["digest_payload"]
    fields = payload["fields"]
    return {
        "resource": {"course_id": "101", "kind": "syllabus"},
        "owner_object": {"kind": fields["owner_kind"], "provider_id": "101"},
        "object_fields": fields["object_fields"],
        "metadata": {
            "title": payload["title"],
            "format": fields["format"],
            "extractor_version": fields["extractor_version"],
            "provider_updated_at": None,
            "total_pages": fields["total_pages"],
            "total_characters": fields["total_characters"],
            "coverage": payload["coverage"],
            "missing": payload["missing"],
        },
        "manifest": fields["slots"],
        "parts": vector["parts"],
        "extractor_versions": ("fixture.v1",),
    }


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["name"])
def test_agreed_root_vectors_recompute_original_bytes_and_digest(vector):
    result = validate_canvas_document(**arguments(vector))
    assert result.canonical_bytes == vector["canonical_utf8"].encode()
    assert result.document_digest == vector["sha256"]
    assert result.payload == vector["digest_payload"]
    assert "".join(s.text for s in result.sections.sections) == vector["normalized_text"]


def test_identity_and_provider_updated_time_are_outside_root_but_still_validated():
    data = arguments()
    original = validate_canvas_document(**data)
    data["resource"]["course_id"] = "102"
    data["owner_object"]["provider_id"] = "other-source"
    data["metadata"]["provider_updated_at"] = "2026-01-01T01:00:00+01:00"
    changed = validate_canvas_document(**data)
    assert changed.document_digest == original.document_digest
    assert changed.course_id == "102" and changed.provider_id == "other-source"
    assert changed.provider_updated_at == data["metadata"]["provider_updated_at"]


def test_input_and_payload_mutation_cannot_change_validated_root():
    data = arguments()
    result = validate_canvas_document(**data)
    data["manifest"][0]["end"] = 999
    data["parts"][0]["text"] = "different"
    payload = result.payload
    payload["fields"]["object_fields"]["source_format"] = "modified"
    assert result.payload["fields"]["object_fields"]["source_format"] == "text"
    assert result.sections.sections[0].text == "Café\n📚"
    with pytest.raises(FrozenInstanceError):
        result.canonical_bytes = b"changed"


@pytest.mark.parametrize("container", ["resource", "owner_object", "metadata", "object_fields"])
@pytest.mark.parametrize("change", ["extra", "missing"])
def test_exact_header_keys(container, change):
    data = arguments()
    if change == "extra":
        data[container]["unreviewed"] = "ignored?"
    else:
        del data[container][next(iter(data[container]))]
    with pytest.raises(ValueError):
        validate_canvas_document(**data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "x" * 301),
        ("title", "\ud800"),
        ("title", 1),
        ("title", "\u0344" * 151),
        ("format", "pdf"),
        ("format", []),
        ("format", None),
        ("extractor_version", "unconfigured"),
        ("extractor_version", " "),
        ("extractor_version", "x" * 65),
        ("extractor_version", "\ud800"),
        ("provider_updated_at", "2026-01-01"),
        ("provider_updated_at", True),
        ("provider_updated_at", "2026-02-30T00:00:00Z"),
        ("total_pages", True),
        ("total_pages", 1),
        ("total_characters", True),
        ("total_characters", "6"),
        ("total_characters", 200001),
        ("total_characters", 7),
        ("coverage", "snapshot"),
        ("coverage", []),
        ("missing", ["unsafe reason"]),
        ("missing", [True]),
        ("missing", ["gap"] * 51),
        ("missing", None),
    ],
)
def test_metadata_rejects_invalid_types_bounds_and_unknown_formats(field, value):
    data = arguments()
    data["metadata"][field] = value
    with pytest.raises(ValueError):
        validate_canvas_document(**data)


@pytest.mark.parametrize("versions", [None, [], (), frozenset(), ("unknown",), (True,), (" ",)])
def test_only_trusted_nonempty_extractor_configuration_is_accepted(versions):
    with pytest.raises(ValueError):
        validate_canvas_document(**(arguments() | {"extractor_versions": versions}))


@pytest.mark.parametrize(
    "container,field,value",
    [
        ("resource", "course_id", "0"),
        ("resource", "course_id", 101),
        ("resource", "kind", "announcements"),
        ("resource", "kind", "files"),
        ("resource", "kind", []),
        ("owner_object", "kind", "page"),
        ("owner_object", "kind", []),
        ("owner_object", "provider_id", "bad/id"),
        ("owner_object", "provider_id", True),
    ],
)
def test_invalid_identity_and_mismatched_resource_pairs(container, field, value):
    data = arguments()
    data[container][field] = value
    with pytest.raises(ValueError):
        validate_canvas_document(**data)


@pytest.mark.parametrize("change", ["hash", "offset", "page", "text", "duplicate", "extra", "nfc"])
def test_tampered_manifest_and_parts_never_produce_root(change):
    data = arguments()
    if change == "hash":
        data["manifest"][0]["text_sha256"] = "0" * 64
    if change == "offset":
        data["manifest"][0]["start"] = 1
    if change == "page":
        data["manifest"][0]["page"] = 1
    if change == "text":
        data["parts"][0]["text"] = "Changed"
    if change == "duplicate":
        data["parts"].append(deepcopy(data["parts"][0]))
    if change == "extra":
        data["parts"][0]["download_url"] = "https://example.invalid"
    if change == "nfc":
        text = "Cafe\u0301\n📚"
        data["parts"][0]["text"] = text
        data["manifest"][0]["text_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        data["manifest"][0]["end"] = data["metadata"]["total_characters"] = len(text)
    with pytest.raises(ValueError):
        validate_canvas_document(**data)


@pytest.mark.parametrize(
    "change",
    ["blank_title", "missing", "page_gap", "zero_text", "zero_without_gap", "pdf_without_pages"],
)
def test_incomplete_evidence_cannot_be_certified_complete(change):
    data = arguments(
        VECTORS[4] if change == "page_gap" else VECTORS[5] if change.startswith("zero") else None
    )
    if change == "blank_title":
        data["metadata"]["title"] = " \n"
    if change == "missing":
        data["metadata"]["missing"] = ["unread"]
    if change in {"page_gap", "zero_text"}:
        data["metadata"]["coverage"] = "complete"
        data["metadata"]["missing"] = []
    if change == "zero_without_gap":
        data["metadata"]["missing"] = []
    if change == "pdf_without_pages":
        data["metadata"]["format"] = "pdf_text"
    with pytest.raises(ValueError):
        validate_canvas_document(**data)


def assignment_data():
    data = arguments()
    data["resource"]["kind"] = "assignments"
    data["owner_object"]["kind"] = "assignment"
    data["object_fields"] = {
        "due_at": "2026-01-01T01:00:00+01:00",
        "unlock_at": None,
        "lock_at": None,
        "points_possible": "10.00",
        "submission_types": ["online_upload"],
        "rubric": [{"id": "r1", "description": "Cite evidence", "points": "5.0", "ratings": []}],
        "published": True,
    }
    return data


def test_assignment_dates_and_rubric_canonicalization_are_reused_and_bound_into_root():
    data = assignment_data()
    original = validate_canvas_document(**data)
    fields = original.payload["fields"]["object_fields"]
    assert fields["due_at"] == "2026-01-01T00:00:00.000000Z"
    assert fields["points_possible"] == "10" and fields["rubric"][0]["points"] == "5"
    data["object_fields"]["due_at"] = "2026-01-01T00:00:00Z"
    assert validate_canvas_document(**data).document_digest == original.document_digest
    data["object_fields"]["due_at"] = "2026-01-02T00:00:00Z"
    assert validate_canvas_document(**data).document_digest != original.document_digest
    data["object_fields"]["due_at"] = fields["due_at"]
    data["object_fields"]["rubric"][0]["description"] = "Now include an example"
    assert validate_canvas_document(**data).document_digest != original.document_digest


@pytest.mark.parametrize(
    "field,value",
    [
        ("published", 1),
        ("points_possible", 10),
        ("due_at", "2026-01-01"),
        ("submission_types", ["z", "a"]),
        ("rubric", [{"id": "broken"}]),
    ],
)
def test_document_assignment_retains_schema1_field_rejection(field, value):
    data = assignment_data()
    data["object_fields"][field] = value
    with pytest.raises(ValueError):
        validate_canvas_document(**data)


def file_data():
    data = arguments()
    data["resource"]["kind"] = "files"
    data["owner_object"] = {"kind": "file", "provider_id": "17"}
    data["object_fields"] = {"filename": "Cafe\u0301.txt", "content_type": "text/plain"}
    return data


def test_file_fields_and_page_resource_are_validated_without_provider_io():
    result = validate_canvas_document(**file_data())
    assert result.payload["fields"]["object_fields"]["filename"] == "Café.txt"
    data = arguments()
    data["resource"]["kind"] = "pages"
    data["owner_object"]["kind"] = "page"
    assert validate_canvas_document(**data).owner_kind == "page"


@pytest.mark.parametrize(
    "filename,content_type",
    [
        ("a/b", "text/plain"),
        ("a\\b", "text/plain"),
        ("a\x00b", "text/plain"),
        ("", "text/plain"),
        ("x" * 301, "text/plain"),
        ("x", "application/zip"),
        ("x", []),
    ],
)
def test_invalid_file_fields(filename, content_type):
    data = file_data()
    data["object_fields"] = {"filename": filename, "content_type": content_type}
    with pytest.raises(ValueError):
        validate_canvas_document(**data)


def test_file_provider_id_must_be_numeric_and_unknown_metadata_never_hashes():
    data = file_data()
    data["owner_object"]["provider_id"] = "syllabus.pdf"
    with pytest.raises(ValueError):
        validate_canvas_document(**data)
    data = file_data()
    data["metadata"]["url"] = "https://example.invalid"
    with pytest.raises(ValueError):
        validate_canvas_document(**data)


def test_full_size_document_is_validated_without_short_text_clipping():
    from dataclasses import asdict

    from shared.document_sections import split_document_text

    data = arguments()
    document = split_document_text("📚" * 200_000)
    data["manifest"], data["parts"] = [], []
    for section in document.sections:
        row = asdict(section)
        data["parts"].append({"slot": row["slot"], "text": row.pop("text")})
        data["manifest"].append(row)
    data["metadata"]["total_characters"] = 200_000
    result = validate_canvas_document(**data)
    assert result.sections.total_characters == 200_000
    assert sum(len(s.text) for s in result.sections.sections) == 200_000
    assert result.payload["content"] == ""  # Body is represented by verified slot hashes.
    assert result.payload["fields"]["total_characters"] == 200_000


@pytest.mark.parametrize("state", ["partial", "restricted", "unsupported"])
def test_zero_text_preserves_gap_and_never_invents_content(state):
    data = arguments(VECTORS[5])
    data["metadata"]["coverage"] = state
    result = validate_canvas_document(**data)
    assert result.sections.sections == ()
    assert result.payload["coverage"] == state
    assert result.payload["missing"] == ["image_only"]


def test_missing_codes_are_canonical_and_coverage_changes_identity():
    data = arguments()
    original = validate_canvas_document(**data)
    data["metadata"].update(coverage="partial", missing=["z_gap", "a_gap", "z_gap"])
    partial = validate_canvas_document(**data)
    assert partial.document_digest != original.document_digest
    assert partial.payload["missing"] == ["a_gap", "z_gap"]
    data["metadata"]["missing"] = ["a_gap", "z_gap"]
    assert validate_canvas_document(**data).document_digest == partial.document_digest


@pytest.mark.parametrize("content_type", ["application/pdf", "text/plain", "text/html"])
def test_all_agreed_mime_types_are_retained(content_type):
    data = file_data()
    data["object_fields"]["content_type"] = content_type
    assert (
        validate_canvas_document(**data).payload["fields"]["object_fields"]["content_type"]
        == content_type
    )
