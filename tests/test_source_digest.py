import json
from copy import deepcopy
from pathlib import Path

import pytest

from contracts.source_digest import canonical_source_bytes, source_digest

VECTORS = json.loads(
    (Path(__file__).parent / "fixtures/source_digest_v1.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("vector", VECTORS, ids=lambda row: row["name"])
def test_fixed_cross_language_vectors(vector):
    assert canonical_source_bytes(vector["input"]).decode() == vector["canonical_utf8"]
    assert source_digest(vector["input"]) == vector["sha256"]


def test_equivalent_unicode_line_endings_dates_and_missing_order():
    first = deepcopy(VECTORS[0]["input"])
    second = dict(reversed(list(first.items())))
    first["content"] = "Cafe\u0301\r\nLine 2\r"
    second["content"] = "Café\nLine 2\n"
    first["fields"] = {"due_at": "2026-11-02T00:59:00-05:00"}
    second["fields"] = {"due_at": "2026-11-02T05:59:00.000000Z"}
    first["missing"] = ["rubric", "file", "rubric"]
    second["missing"] = ["file", "rubric"]
    assert source_digest(first) == source_digest(second)


@pytest.mark.parametrize(
    "field,value",
    [
        ("content", "Different instructions"),
        ("title", "New title"),
        ("fields", {"due_at": "2026-11-03T05:59:00Z"}),
        ("coverage", "partial"),
        ("missing", ["rubric"]),
    ],
)
def test_meaningful_content_or_coverage_change_changes_digest(field, value):
    payload = deepcopy(VECTORS[0]["input"])
    payload[field] = value
    assert source_digest(payload) != VECTORS[0]["sha256"]


@pytest.mark.parametrize(
    "metadata", ["last_checked", "provider_updated_at", "reference", "user_id"]
)
def test_collection_or_identity_metadata_cannot_enter_content_digest(metadata):
    payload = deepcopy(VECTORS[0]["input"])
    payload[metadata] = "not-content"
    with pytest.raises(ValueError, match="Exact digest envelope"):
        source_digest(payload)


@pytest.mark.parametrize("value", [1.25, float("nan"), float("inf"), {1: "bad"}])
def test_nonportable_values_are_rejected(value):
    payload = deepcopy(VECTORS[0]["input"])
    payload["fields"] = {"nested": value}
    with pytest.raises(ValueError):
        source_digest(payload)


def test_unicode_key_collision_is_rejected():
    payload = deepcopy(VECTORS[0]["input"])
    payload["fields"] = {"é": 1, "e\u0301": 2}
    with pytest.raises(ValueError, match="collision"):
        source_digest(payload)


def test_large_integers_must_be_encoded_as_provider_strings():
    payload = deepcopy(VECTORS[0]["input"])
    payload["fields"] = {"provider_value": 2**53}
    with pytest.raises(ValueError, match="interoperable range"):
        source_digest(payload)
    payload["fields"] = {"provider_value": str(2**53)}
    assert source_digest(payload)


@pytest.mark.parametrize("date", ["2026-11-02", "2026-11-02T05:59:00", "tomorrow", 1, True])
def test_dates_cannot_be_naive_or_guessed(date):
    payload = deepcopy(VECTORS[0]["input"])
    payload["fields"] = {"due_at": date}
    with pytest.raises(ValueError):
        source_digest(payload)


def test_content_spacing_and_list_order_are_preserved():
    payload = deepcopy(VECTORS[0]["input"])
    payload["content"] += " "
    assert source_digest(payload) != VECTORS[0]["sha256"]
    payload["fields"] = {"rubric": ["one", "two"]}
    first = source_digest(payload)
    payload["fields"]["rubric"].reverse()
    assert source_digest(payload) != first


@pytest.mark.parametrize("offset", ["+01:60", "-01:99", "+24:00", "-24:00", "+０１:００"])
def test_invalid_rfc3339_offset_components_are_not_normalized(offset):
    payload = deepcopy(VECTORS[0]["input"])
    payload["fields"] = {"due_at": "2026-01-01T00:00:00" + offset}
    with pytest.raises(ValueError, match="RFC3339"):
        source_digest(payload)


def test_valid_extreme_offset_keeps_microseconds_across_year_boundary():
    first = deepcopy(VECTORS[0]["input"])
    second = deepcopy(first)
    first["fields"] = {"due_at": "2026-01-01T00:00:00.123456+23:59"}
    second["fields"] = {"due_at": "2025-12-31T00:01:00.123456Z"}
    assert source_digest(first) == source_digest(second)
