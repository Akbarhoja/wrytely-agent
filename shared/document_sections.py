"""Internal immutable text sections; no parsing, persistence, identity or wire activation.

Implements only the agreed section/manifest invariants. Callers must separately
verify ownership, pinned observation/root identity, coverage and freshness.
"""

import hashlib
import re
from dataclasses import dataclass

from contracts.source_digest import _text

MAX_CHARACTERS = 200_000
MAX_SECTIONS = 512
MAX_SECTION_CHARACTERS = 24_000
MAX_READ_CHARACTERS = 40_000
MAX_PAGES = 200


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid document section bounds")


def _normalized(value):
    # Bound before normalization as well as afterwards; never return a prefix.
    if not isinstance(value, str) or len(value) > 2 * MAX_CHARACTERS:
        raise ValueError("Document text limit")
    try:
        if len(value.encode("utf-8")) > 1024 * 1024:
            raise ValueError("Document text limit")
        result = _text(value)
    except UnicodeError:
        raise ValueError("Invalid document Unicode") from None
    if len(result) > MAX_CHARACTERS:
        raise ValueError("Document text limit")
    return result


def _exact(value, keys):
    if not isinstance(value, dict) or value.keys() != set(keys):
        raise ValueError("Exact document section fields required")


@dataclass(frozen=True)
class DocumentSection:
    slot: int
    start: int
    end: int
    page: int | None
    text: str
    text_sha256: str

    def __post_init__(self):
        _integer(self.slot, 0, MAX_SECTIONS - 1)
        _integer(self.start, 0, MAX_CHARACTERS)
        _integer(self.end, self.start + 1, MAX_CHARACTERS)
        if self.page is not None:
            _integer(self.page, 1, MAX_PAGES)
        if (
            not isinstance(self.text, str)
            or not 1 <= len(self.text) <= MAX_SECTION_CHARACTERS
            or self.end - self.start != len(self.text)
            or _normalized(self.text) != self.text
            or not isinstance(self.text_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", self.text_sha256)
            or hashlib.sha256(self.text.encode()).hexdigest() != self.text_sha256
        ):
            raise ValueError("Invalid document section text or hash")


@dataclass(frozen=True)
class DocumentSections:
    sections: tuple[DocumentSection, ...]
    total_characters: int
    total_pages: int | None

    def __post_init__(self):
        _integer(self.total_characters, 0, MAX_CHARACTERS)
        if self.total_pages is not None:
            _integer(self.total_pages, 1, MAX_PAGES)
        if type(self.sections) is not tuple or len(self.sections) > MAX_SECTIONS:
            raise ValueError("Document section count limit")
        end, last_page = 0, 0
        for index, section in enumerate(self.sections):
            if not isinstance(section, DocumentSection):
                raise ValueError("Invalid document section")
            if section.slot != index or section.start != end:
                raise ValueError("Document sections must be ordered and contiguous")
            if self.total_pages is None:
                if section.page is not None:
                    raise ValueError("Non-PDF section cannot have a page")
            elif section.page is None or not last_page <= section.page <= self.total_pages:
                raise ValueError("Invalid document page provenance")
            end, last_page = section.end, section.page or 0
        text = "".join(section.text for section in self.sections)
        if end != self.total_characters or _normalized(text) != text:
            raise ValueError("Document total or whole-text normalization mismatch")

    @property
    def unrepresented_pages(self):
        """Gaps for callers to classify; presence of text never certifies PDF completeness."""
        if self.total_pages is None:
            return ()
        represented = {section.page for section in self.sections}
        return tuple(page for page in range(1, self.total_pages + 1) if page not in represented)


@dataclass(frozen=True)
class DocumentSectionPage:
    sections: tuple[DocumentSection, ...]
    next_slot: int | None
    total_slots: int


def split_document_text(text, *, section_characters=MAX_SECTION_CHARACTERS):
    """Normalize whole non-PDF text before splitting; page-aware producers use validation."""
    _integer(section_characters, 1, MAX_SECTION_CHARACTERS)
    text = _normalized(text)
    count = (len(text) + section_characters - 1) // section_characters
    if count > MAX_SECTIONS:
        raise ValueError("Document section count limit")
    sections = tuple(
        DocumentSection(
            slot=slot,
            start=start,
            end=min(start + section_characters, len(text)),
            page=None,
            text=text[start : start + section_characters],
            text_sha256=hashlib.sha256(
                text[start : start + section_characters].encode()
            ).hexdigest(),
        )
        for slot, start in enumerate(range(0, len(text), section_characters))
    )
    return DocumentSections(sections, len(text), None)


def validate_document_sections(manifest, parts, *, total_characters, total_pages=None):
    """Validate accepted slot/part shapes, hashes and provenance; no root digest or upload API."""
    _integer(total_characters, 0, MAX_CHARACTERS)
    if total_pages is not None:
        _integer(total_pages, 1, MAX_PAGES)
    if (
        type(manifest) not in (list, tuple)
        or type(parts) not in (list, tuple)
        or len(manifest) > MAX_SECTIONS
        or len(parts) != len(manifest)
    ):
        raise ValueError("Document manifest/part count mismatch")
    text_by_slot = {}
    for part in parts:
        _exact(part, ("slot", "text"))
        _integer(part["slot"], 0, MAX_SECTIONS - 1)
        if part["slot"] in text_by_slot:
            raise ValueError("Duplicate document part")
        text_by_slot[part["slot"]] = part["text"]
    sections = []
    for index, slot in enumerate(manifest):
        _exact(slot, ("slot", "start", "end", "page", "text_sha256"))
        _integer(slot["slot"], 0, MAX_SECTIONS - 1)
        if slot["slot"] != index or index not in text_by_slot:
            raise ValueError("Document manifest order or missing part")
        sections.append(DocumentSection(**slot, text=text_by_slot[index]))
    return DocumentSections(tuple(sections), total_characters, total_pages)


def page_document_sections(document, *, first_slot=0, limit=10):
    """Page an immutable, already-authorized document; whole slots only, explicit continuation."""
    if not isinstance(document, DocumentSections):
        raise ValueError("Validated document sections required")
    _integer(first_slot, 0, len(document.sections))
    _integer(limit, 1, 20)
    sections, size, next_slot = [], 0, first_slot
    for section in document.sections[first_slot : first_slot + limit]:
        if size + len(section.text) > MAX_READ_CHARACTERS:
            break
        sections.append(section)
        size += len(section.text)
        next_slot += 1
    return DocumentSectionPage(
        tuple(sections),
        next_slot if next_slot < len(document.sections) else None,
        len(document.sections),
    )
