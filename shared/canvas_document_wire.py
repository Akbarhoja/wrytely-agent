"""Pure agreed v2 document-root validation; no upload, authorization or persistence."""

import hashlib
import json
import re
from dataclasses import dataclass

from contracts.canvas_document_publication import PAIRS, document_kind_allowed
from contracts.canvas_evidence import EvidenceItem
from contracts.canvas_sync import DiscoveryBatch, course_id
from contracts.source_digest import _text, canonical_source_bytes
from shared.document_sections import DocumentSections, validate_document_sections

_PAIRS = PAIRS
_METADATA = {
    "title",
    "format",
    "extractor_version",
    "provider_updated_at",
    "total_pages",
    "total_characters",
    "coverage",
    "missing",
}


def _keys(value, names):
    if type(value) is not dict or value.keys() != set(names):
        raise ValueError("Exact document fields required")


def _bounded_text(value, limit, *, nonblank=False):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("Invalid document text")
    try:
        normalized = _text(value)
    except UnicodeError:
        raise ValueError("Invalid document Unicode") from None
    if len(normalized) > limit or (nonblank and not normalized.strip()):
        raise ValueError("Invalid document text")
    return normalized


@dataclass(frozen=True)
class ValidatedCanvasDocument:
    course_id: str
    resource_kind: str
    owner_kind: str
    provider_id: str
    provider_updated_at: str | None
    sections: DocumentSections
    canonical_bytes: bytes
    document_digest: str

    @property
    def payload(self):
        """A new detached canonical root; callers cannot mutate validated state."""
        return json.loads(self.canonical_bytes)


def validate_canvas_document_header(
    *, resource, owner_object, object_fields, metadata, manifest, extractor_versions
):
    """Validate/detach immutable upload metadata; text integrity is deferred to finish."""
    _keys(resource, ("course_id", "kind"))
    _keys(owner_object, ("kind", "provider_id"))
    _keys(metadata, _METADATA)
    course_id(resource["course_id"])
    kind = owner_object["kind"]
    if (
        not isinstance(resource["kind"], str)
        or resource["kind"] not in _PAIRS
        or not isinstance(kind, str)
        or not document_kind_allowed(resource["kind"], kind)
    ):
        raise ValueError("Invalid document resource/owner pair")
    provider_id = owner_object["provider_id"]
    if not isinstance(provider_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", provider_id):
        raise ValueError("Invalid document provider ID")
    if kind == "file":
        course_id(provider_id)  # Canvas file IDs are numeric; identity is not a root hash.

    title = _bounded_text(metadata["title"], 300)
    format_name = metadata["format"]
    if not isinstance(format_name, str) or format_name not in {"text", "html_text", "pdf_text"}:
        raise ValueError("Invalid document format")
    version = _bounded_text(metadata["extractor_version"], 64, nonblank=True)
    if (
        type(extractor_versions) not in (tuple, frozenset)
        or not extractor_versions
        or any(_bounded_text(v, 64, nonblank=True) != v for v in extractor_versions)
        or version not in extractor_versions
    ):
        raise ValueError("Unconfigured document extractor")
    updated_at = metadata["provider_updated_at"]
    if updated_at is not None:
        if not isinstance(updated_at, str):
            raise ValueError("Invalid document timestamp")
        DiscoveryBatch.aware_timestamp(updated_at)
    total_pages = metadata["total_pages"]
    if (format_name == "pdf_text") != (total_pages is not None):
        raise ValueError("Document format/page mismatch")
    coverage, missing = metadata["coverage"], metadata["missing"]
    if (
        not isinstance(coverage, str)
        or coverage not in {"complete", "partial", "restricted", "unsupported"}
        or type(missing) is not list
        or len(missing) > 50
        or any(
            not isinstance(m, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,127}", m)
            for m in missing
        )
    ):
        raise ValueError("Invalid document coverage")
    if kind == "file":
        _keys(object_fields, ("filename", "content_type"))
        filename = _bounded_text(object_fields["filename"], 300, nonblank=True)
        content_type = object_fields["content_type"]
        if (
            any(c in filename for c in ("/", "\\", "\x00"))
            or not isinstance(content_type, str)
            or not re.fullmatch(r"[a-z0-9.+-]{1,64}/[a-z0-9.+-]{1,128}", content_type)
        ):
            raise ValueError("Invalid document file fields")
        if content_type not in {"application/pdf", "text/plain", "text/html"} and (
            coverage != "unsupported"
            or manifest
            or metadata["total_characters"] != 0
            or "unsupported_format" not in missing
        ):
            raise ValueError("Unsupported file must remain an empty explicit gap")
        fields = {"filename": filename, "content_type": content_type}
    else:
        # Reuse schema1 academic field validation/canonicalization, without its
        # short-body/complete constraint: the full document was validated above.
        fields = EvidenceItem(
            kind=kind,
            provider_id=provider_id,
            provider_updated_at=updated_at,
            title=title,
            reference="document:validation",
            fields=object_fields,
            content="",
            coverage="partial",
            missing=[],
        ).payload(kind)["fields"]
    # Header validation cannot verify text hashes until parts arrive. It still
    # rejects malformed offsets, page provenance and section bounds at begin.
    if (
        type(metadata["total_characters"]) is not int
        or not 0 <= metadata["total_characters"] <= 200000
    ):
        raise ValueError("Invalid document character count")
    if total_pages is not None and (type(total_pages) is not int or not 1 <= total_pages <= 200):
        raise ValueError("Invalid document page count")
    if type(manifest) is not list or len(manifest) > 512:
        raise ValueError("Invalid document manifest")
    end, last_page, pages = 0, 0, set()
    for index, slot in enumerate(manifest):
        _keys(slot, ("slot", "start", "end", "page", "text_sha256"))
        if (
            any(type(slot[k]) is not int for k in ("slot", "start", "end"))
            or slot["slot"] != index
            or slot["start"] != end
            or not 1 <= slot["end"] - slot["start"] <= 24000
            or slot["end"] > 200000
            or not isinstance(slot["text_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", slot["text_sha256"])
        ):
            raise ValueError("Invalid document manifest")
        page = slot["page"]
        if total_pages is None:
            if page is not None:
                raise ValueError("Non-PDF document page")
        elif type(page) is not int or not max(1, last_page) <= page <= total_pages:
            raise ValueError("Invalid document page provenance")
        if page is not None:
            last_page = page
            pages.add(page)
        end = slot["end"]
    if end != metadata["total_characters"]:
        raise ValueError("Document manifest total mismatch")
    gaps = total_pages is not None and len(pages) != total_pages
    if coverage == "complete" and (not title.strip() or not end or gaps or missing):
        raise ValueError("Complete document header has gaps")
    if (not end or gaps) and not missing:
        raise ValueError("Document header requires missing evidence")
    # JSON roundtrip detaches all nested inputs and rejects non-JSON values.
    return json.loads(
        json.dumps(
            {
                "resource": resource,
                "owner_object": owner_object,
                "object_fields": fields,
                "metadata": {**metadata, "title": title, "extractor_version": version},
                "manifest": manifest,
            },
            ensure_ascii=False,
            allow_nan=False,
        )
    )


def validate_canvas_document(
    *, resource, owner_object, object_fields, metadata, manifest, parts, extractor_versions
):
    """Validate a fully assembled root against the agreed #118 design.

    Configured extractor IDs come from a trusted caller, never from the source.
    Identity/scan/lease/expiry/quota checks and staged wire parsing remain separate.
    No raw file or URL fetching, extraction, source activation or clipping occurs.
    """
    header = validate_canvas_document_header(
        resource=resource,
        owner_object=owner_object,
        object_fields=object_fields,
        metadata=metadata,
        manifest=manifest,
        extractor_versions=extractor_versions,
    )
    resource, owner_object, metadata, manifest = (
        header["resource"],
        header["owner_object"],
        header["metadata"],
        header["manifest"],
    )
    selected_course, kind, provider_id = (
        resource["course_id"],
        owner_object["kind"],
        owner_object["provider_id"],
    )
    title, format_name, version = (
        metadata["title"],
        metadata["format"],
        metadata["extractor_version"],
    )
    updated_at = metadata["provider_updated_at"]
    coverage, missing, fields = metadata["coverage"], metadata["missing"], header["object_fields"]
    document = validate_document_sections(
        manifest,
        parts,
        total_characters=metadata["total_characters"],
        total_pages=metadata["total_pages"],
    )
    has_text = any(section.text.strip() for section in document.sections)
    if coverage == "complete" and (
        missing or not title.strip() or not has_text or document.unrepresented_pages
    ):
        raise ValueError("Complete document requires text, title and all pages without gaps")
    if (not has_text or document.unrepresented_pages) and not missing:
        raise ValueError("Empty or page-gapped document requires missing evidence")

    encoded = canonical_source_bytes(
        {
            "digest_version": 1,
            "kind": "document",
            "title": title,
            "content": "",
            "fields": {
                "format": format_name,
                "extractor_version": version,
                "total_pages": document.total_pages,
                "total_characters": document.total_characters,
                "slots": manifest,
                "owner_kind": kind,
                "object_fields": fields,
            },
            "coverage": coverage,
            "missing": missing,
        }
    )
    return ValidatedCanvasDocument(
        selected_course,
        resource["kind"],
        kind,
        provider_id,
        updated_at,
        document,
        encoded,
        hashlib.sha256(encoded).hexdigest(),
    )
