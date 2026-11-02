"""Bounded isolated extraction and scoped file conversion; synthetic bytes only."""

import base64
import io

import pytest
import test_canvas_evidence as evidence
import test_canvas_sync as sync
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from test_canvas_document_upload_api import checked, client_for, post
from test_canvas_sync import device as device

from integrations.canvas.pdf_extract import extract_pdf


def sample_pdf():
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 250 Td (Synthetic syllabus.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_original_page_text_is_extracted_in_a_bounded_child():
    result = extract_pdf(sample_pdf())
    assert len(result["pages"]) == 1 and "Synthetic syllabus." in result["pages"][0]
    assert "pdf_layout_and_images_unread" in result["missing"]


@pytest.mark.parametrize(
    "content", [b"not pdf", b"%PDF-broken", b"%PDF-" + b"x" * (5 * 1024 * 1024)]
)
def test_invalid_and_oversized_pdf_never_fabricates_text(content):
    assert extract_pdf(content)["pages"] == []


def body(device, content=b"Visible original file.", mime="text/plain"):
    evidence.prepare(device, kinds=["files"])
    context = device[0].canvas_connection_context(device[1]["ingestion_bearer"], sync.ORIGIN)
    return {
        "schema_version": 2,
        "operation": "extract_file",
        "origin": sync.ORIGIN,
        "connection_id": context["connection_id"],
        "generation": context["generation"],
        "scope_revision": context["scope_revision"],
        "course_id": "101",
        "file_id": "90",
        "content_type": mime,
        "data": base64.b64encode(content).decode(),
    }


@pytest.mark.parametrize(
    "mime,content",
    [
        ("text/plain", b"Visible original file."),
        ("text/html", b"<p>Read this.</p><script>PRIVATE</script>"),
        ("application/pdf", None),
    ],
)
def test_actual_scoped_file_extraction_returns_original_text_or_pages(device, mime, content):
    request = body(device, sample_pdf() if content is None else content, mime)
    response = checked(
        post(
            client_for(device, versions=("canvas.text.v1", "canvas.html.v1", "canvas.pdf.v1")),
            device,
            "/file-extract",
            request,
        )
    )
    assert response["schema_version"] == 2 and "PRIVATE" not in str(response)
    if mime == "application/pdf":
        assert "Synthetic syllabus." in response["source"]["pages"][0]
    else:
        assert response["source"]["text"]


@pytest.mark.parametrize(
    "field,value,status",
    [
        ("course_id", "102", 409),
        ("generation", 999, 409),
        ("scope_revision", 999, 409),
        ("data", "not-base64!", 400),
        ("content_type", ["text/plain"], 400),
    ],
)
def test_file_extraction_rejects_invalid_scope_and_wire(device, field, value, status):
    request = body(device)
    request[field] = value
    checked(
        post(client_for(device, versions=("canvas.text.v1",)), device, "/file-extract", request),
        status,
    )


def test_file_extraction_default_remains_off(device):
    checked(post(client_for(device), device, "/file-extract", body(device)), 503)


def test_revocation_during_pdf_extraction_discards_the_result(device, monkeypatch):
    request = body(device, sample_pdf(), "application/pdf")

    def revoked(_content):
        device[0].rotate_or_revoke("user_alice", device[1]["connection_id"])
        return {"pages": ["PRIVATE_RESULT_MUST_NOT_LEAVE"], "missing": ["pdf_text_only"]}

    monkeypatch.setattr("app.canvas_document_api.extract_pdf", revoked)
    response = post(
        client_for(device, versions=("canvas.pdf.v1",)), device, "/file-extract", request
    )
    checked(response, 401)
    assert "PRIVATE_RESULT_MUST_NOT_LEAVE" not in response.text
