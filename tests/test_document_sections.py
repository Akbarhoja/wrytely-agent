import hashlib
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict

import pytest

from shared.document_sections import (
    DocumentSection,
    DocumentSections,
    page_document_sections,
    split_document_text,
    validate_document_sections,
)


def records(document):
    manifest, parts = [], []
    for section in document.sections:
        entry = asdict(section)
        parts.append({"slot": entry["slot"], "text": entry.pop("text")})
        manifest.append(entry)
    return manifest, parts


def test_normalize_whole_text_before_splitting_and_hash_exact_utf8():
    document = split_document_text("Cafe\u0301\r\nA📚B\r", section_characters=3)
    expected = "Café\nA📚B\n"
    assert "".join(s.text for s in document.sections) == expected
    assert document.total_characters == len(expected)
    for index, section in enumerate(document.sections):
        assert section.slot == index and section.page is None
        assert expected[section.start : section.end] == section.text
        assert section.end - section.start == len(section.text)
        assert hashlib.sha256(section.text.encode()).hexdigest() == section.text_sha256


def test_full_long_document_is_retrievable_without_prefix_completion():
    text = "📚" * 200_000
    document = split_document_text(text)
    first, returned = 0, []
    while True:
        page = page_document_sections(document, first_slot=first, limit=20)
        assert 0 < sum(len(s.text) for s in page.sections) <= 40_000
        returned.extend(page.sections)
        if page.next_slot is None:
            break
        assert page.next_slot > first
        first = page.next_slot
    assert tuple(returned) == document.sections
    assert "".join(s.text for s in returned) == text
    assert document.total_characters == 200_000


def test_paging_keeps_whole_slots_and_explicit_end():
    document = split_document_text("x" * 60_000, section_characters=20_000)
    page = page_document_sections(document, limit=20)
    assert len(page.sections) == 2 and page.next_slot == 2 and page.total_slots == 3
    last = page_document_sections(document, first_slot=2)
    assert len(last.sections) == 1 and last.next_slot is None
    end = page_document_sections(document, first_slot=3)
    assert end.sections == () and end.next_slot is None and end.total_slots == 3


def test_manifest_is_immutable_and_part_arrival_order_does_not_change_sections():
    original = split_document_text("Original source text", section_characters=5)
    manifest, parts = records(original)
    result = validate_document_sections(manifest, list(reversed(parts)), total_characters=20)
    assert result == original
    manifest[0]["start"] = 999
    parts[0]["text"] = "Changed"
    assert result == original
    with pytest.raises(FrozenInstanceError):
        result.total_characters = 0
    with pytest.raises(FrozenInstanceError):
        result.sections[0].text = "Changed"


def test_pdf_page_provenance_and_gaps_are_preserved_without_inventing_text():
    # Already extracted text with explicit caller-supplied page boundaries, no PDF parsing.
    sections = (
        DocumentSection(0, 0, 1, 1, "A", hashlib.sha256(b"A").hexdigest()),
        DocumentSection(1, 1, 3, 3, "📚B", hashlib.sha256("📚B".encode()).hexdigest()),
    )
    manifest, parts = records(DocumentSections(sections, 3, 3))
    result = validate_document_sections(manifest, parts, total_characters=3, total_pages=3)
    assert result.unrepresented_pages == (2,)
    assert [s.page for s in page_document_sections(result).sections] == [1, 3]
    assert "".join(s.text for s in result.sections) == "A📚B"


def test_empty_text_is_not_fabricated_as_a_section_or_a_complete_pdf():
    assert split_document_text("").sections == ()
    document = validate_document_sections([], [], total_characters=0, total_pages=2)
    assert document.unrepresented_pages == (1, 2)
    assert page_document_sections(document).sections == ()


@pytest.mark.parametrize(
    "value", [None, 1, b"text", "\ud800", "\udfff", "x" * 200_001, "\u0344" * 100_001]
)
def test_invalid_or_normalized_oversize_text_rejects_whole_result(value):
    with pytest.raises(ValueError):
        split_document_text(value)


@pytest.mark.parametrize("bound", [True, False, 0, -1, 24_001, 1.5, "10"])
def test_invalid_section_limit_rejects(bound):
    with pytest.raises(ValueError):
        split_document_text("text", section_characters=bound)


def test_too_many_small_sections_rejects_instead_of_truncating():
    with pytest.raises(ValueError, match="count limit"):
        split_document_text("x" * 513, section_characters=1)


@pytest.mark.parametrize(
    "name,value",
    [
        ("first_slot", True),
        ("first_slot", -1),
        ("first_slot", 2),
        ("limit", True),
        ("limit", 0),
        ("limit", 21),
        ("limit", "1"),
    ],
)
def test_bad_read_bounds_do_not_create_a_page(name, value):
    with pytest.raises(ValueError):
        page_document_sections(split_document_text("text"), **{name: value})


@pytest.mark.parametrize(
    "mutation",
    [
        "gap",
        "overlap",
        "reorder",
        "hash",
        "unknown_slot",
        "unknown_part",
        "duplicate_part",
        "missing_part",
        "extra_part",
        "non_nfc",
        "wrong_total",
        "bool_offset",
        "bool_page",
        "non_pdf_page",
        "decreasing_page",
        "too_large_page",
        "null_pdf_page",
    ],
)
def test_manifest_tampering_and_unreliable_page_provenance_reject(mutation):
    document = split_document_text("abcd", section_characters=2)
    manifest, parts = records(document)
    total, pages = 4, None
    if mutation == "gap":
        manifest[1]["start"] += 1
    elif mutation == "overlap":
        manifest[1]["start"] -= 1
    elif mutation == "reorder":
        manifest.reverse()
    elif mutation == "hash":
        manifest[0]["text_sha256"] = "0" * 64
    elif mutation == "unknown_slot":
        manifest[0]["url"] = "https://example.invalid"
    elif mutation == "unknown_part":
        parts[0]["user_id"] = "other"
    elif mutation == "duplicate_part":
        parts[1]["slot"] = 0
    elif mutation == "missing_part":
        parts.pop()
    elif mutation == "extra_part":
        parts.append(deepcopy(parts[0]))
    elif mutation == "non_nfc":
        parts[0]["text"] = "e\u0301"
        manifest[0]["text_sha256"] = hashlib.sha256("e\u0301".encode()).hexdigest()
    elif mutation == "wrong_total":
        total += 1
    elif mutation == "bool_offset":
        manifest[0]["start"] = False
    elif mutation == "bool_page":
        manifest[0]["page"] = True
    elif mutation == "non_pdf_page":
        manifest[0]["page"] = 1
    else:
        pages = 2
        manifest[0]["page"], manifest[1]["page"] = 2, 1
        if mutation == "too_large_page":
            manifest[1]["page"] = 3
        if mutation == "null_pdf_page":
            manifest[1]["page"] = None
    with pytest.raises(ValueError):
        validate_document_sections(manifest, parts, total_characters=total, total_pages=pages)


def test_individually_normalized_parts_cannot_hide_cross_boundary_nfc_change():
    first = DocumentSection(0, 0, 1, None, "e", hashlib.sha256(b"e").hexdigest())
    mark = "\u0301"
    second = DocumentSection(1, 1, 2, None, mark, hashlib.sha256(mark.encode()).hexdigest())
    with pytest.raises(ValueError, match="whole-text normalization"):
        DocumentSections((first, second), 2, None)


@pytest.mark.parametrize(
    "total,pages", [(True, None), (-1, None), (200_001, None), (0, True), (0, 0), (0, 201)]
)
def test_invalid_totals_reject_even_for_zero_parts(total, pages):
    with pytest.raises(ValueError):
        validate_document_sections([], [], total_characters=total, total_pages=pages)


def test_read_does_not_accept_unvalidated_input():
    with pytest.raises(ValueError):
        page_document_sections({"sections": []})
