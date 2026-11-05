from uuid import uuid4

import pytest

from contracts.artifacts import CoursePolicy, DraftArtifact, RubricItem
from runtime.draft_format import check_draft_format

MARKER = (
    "Include this disclosure separately from the word-counted body:\nAI helped; review required."
)


def check(
    body,
    *,
    disclosure="AI helped; review required.",
    source=MARKER,
    quote="Write a 3–5 word draft.",
):
    version = uuid4()
    return check_draft_format(
        DraftArtifact(title="Review", body=body, disclosure=disclosure, citations=[]),
        CoursePolicy(status="disclosure_required", version_id=version, quote="AI permitted."),
        source,
        [RubricItem(version_id=version, quote=quote)],
    )


@pytest.mark.parametrize("words", [3, 4, 5])
def test_separate_disclosure_excluded_and_inclusive_range_passes(words):
    result = check(" ".join(["word"] * words))
    assert result["errors"] == []
    assert result["word_count"] == words
    assert result["disclosure_placement"] == "separate_field"
    assert result["word_ranges"][0]["minimum"] == 3
    assert result["word_ranges"][0]["maximum"] == 5


@pytest.mark.parametrize("words", [2, 6])
def test_word_range_failure_is_concrete(words):
    assert "word_count_out_of_range" in check(" ".join(["word"] * words))["errors"]


@pytest.mark.parametrize("disclosure", ["", "Different disclosure"])
def test_separate_disclosure_requires_exact_source_text(disclosure):
    assert "disclosure_text_mismatch" in check("one two three", disclosure=disclosure)["errors"]


def test_separate_disclosure_cannot_be_silently_inserted_into_body():
    result = check("one two three\nAI helped; review required.")
    assert "disclosure_must_be_separate" in result["errors"]


def test_legacy_disclosure_stays_required_in_body_without_explicit_placement():
    assert (
        "disclosure_missing_from_body" in check("one two three", source="AI permitted.")["errors"]
    )
    result = check(
        "one two three\nAI helped; review required.",
        source="AI permitted.",
        quote="Compare sources.",
    )
    assert result["errors"] == []
    assert result["disclosure_placement"] == "body_and_field"
    assert result["word_count"] == 7


@pytest.mark.parametrize("separator", ["-", "–", "—"])
def test_supported_range_spellings_and_word_count_convention(separator):
    result = check("well-known\tterm\n25%", quote=f"Write a 3{separator}5-word draft.")
    assert result["errors"] == []
    assert result["word_count"] == 3


@pytest.mark.parametrize("quote", ["Write about 5 words.", "At least 3 words.", "Write 5 words."])
def test_unrecognized_numeric_word_requirement_is_not_called_verified(quote):
    assert "word_count_requirement_unparsed" in check("one two three", quote=quote)["errors"]


def test_non_numeric_requirement_does_not_invent_word_limit():
    result = check("one two three", quote="Explain the word entropy.")
    assert result["errors"] == []
    assert result["word_ranges"] == []


def test_multiple_ranges_are_all_enforced_and_conflict_is_explicit():
    result = check("one two three", quote="Write 3–5 words. Write 8–10 words.")
    assert "word_count_bounds_conflict" in result["errors"]


def test_ambiguous_separate_disclosure_does_not_relax_gate():
    source = MARKER + "\n" + MARKER.replace("AI helped; review required.", "Other text.")
    assert "disclosure_format_ambiguous" in check("one two three", source=source)["errors"]
