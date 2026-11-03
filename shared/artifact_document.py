"""Pure inert DOCX serialization reused by private download and typed delivery."""

import io
import re
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML = "http://www.w3.org/XML/1998/namespace"
MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ET.register_namespace("w", W)


def render_docx(draft):
    text = "\n".join([draft.title, draft.body, draft.disclosure])
    if re.search(r"\$\$|\\\[|\\\(|\\(?:frac|begin|sqrt)\b", text):
        raise ValueError("equation_layout_unsupported")
    if any(ord(c) < 32 and c not in "\t\n\r" for c in text):
        raise ValueError("unsupported_document_character")
    root = ET.Element(f"{{{W}}}document")
    body = ET.SubElement(root, f"{{{W}}}body")

    def paragraph(value, *, bold=False):
        if any(
            not (
                ord(c) in (9, 10, 13)
                or 32 <= ord(c) <= 0xD7FF
                or 0xE000 <= ord(c) <= 0xFFFD
                or 0x10000 <= ord(c) <= 0x10FFFF
            )
            for c in value
        ):
            raise ValueError("unsupported_document_character")
        p = ET.SubElement(body, f"{{{W}}}p")
        r = ET.SubElement(p, f"{{{W}}}r")
        if bold:
            ET.SubElement(ET.SubElement(r, f"{{{W}}}rPr"), f"{{{W}}}b")
        ET.SubElement(r, f"{{{W}}}t", {f"{{{XML}}}space": "preserve"}).text = value

    paragraph(draft.title, bold=True)
    for line in draft.body.splitlines():
        paragraph(line)
    if draft.disclosure:
        paragraph("AI assistance disclosure", bold=True)
        paragraph(draft.disclosure)
    if draft.citations:
        paragraph("Source evidence", bold=True)
    for i, citation in enumerate(draft.citations, 1):
        evidence = citation.evidence
        reference = (
            f"Source version {evidence.version_id}"
            if evidence.kind == "legacy"
            else f"Canvas document {evidence.document_version_id}, section {evidence.slot}, "
            f"characters {evidence.start}–{evidence.end}"
        )
        paragraph(f"[{i}] {citation.claim}")
        paragraph(reference)
        paragraph(evidence.quote)
    section = ET.SubElement(body, f"{{{W}}}sectPr")
    ET.SubElement(section, f"{{{W}}}pgSz", {f"{{{W}}}w": "12240", f"{{{W}}}h": "15840"})
    ET.SubElement(
        section,
        f"{{{W}}}pgMar",
        {f"{{{W}}}{key}": "1440" for key in ("top", "bottom", "left", "right")},
    )
    entries = {
        "[Content_Types].xml": (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            b'<Default Extension="rels" '
            b'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            b'<Default Extension="xml" ContentType="application/xml"/>'
            b'<Override PartName="/word/document.xml" '
            b'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            b"</Types>"
        ),
        "_rels/.rels": (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            b'<Relationship Id="rId1" '
            b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            b'officeDocument" '
            b'Target="word/document.xml"/></Relationships>'
        ),
        "word/document.xml": ET.tostring(root, encoding="utf-8", xml_declaration=True),
    }
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        for name, content in entries.items():
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, content)
    return output.getvalue()
