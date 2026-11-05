import hashlib
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from test_telegram import TOKEN, response

from contracts.delivery import ArtifactDeliveryFile
from contracts.templates import ArtifactPayload
from integrations.telegram import TelegramAdapter
from shared.artifact_document import MIME


def checked_file():
    artifact = str(uuid4())
    content = b"PK synthetic checked bytes"
    return ArtifactDeliveryFile(
        ArtifactPayload(
            file_id=str(uuid4()),
            artifact_id=artifact,
            check_id=str(uuid4()),
            filename=f"wrytely-{artifact}.docx",
            media_type=MIME,
            sha256=hashlib.sha256(content).hexdigest(),
            byte_length=len(content),
        ),
        content,
    )


@pytest.mark.parametrize("status,state", [(200, "accepted"), (503, "unknown"), (403, "failed")])
def test_checked_document_uses_exact_bytes_and_one_attempt(status, state):
    file = checked_file()
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url.path.endswith("/sendDocument")
        assert (
            file.content in request.content and file.descriptor.filename.encode() in request.content
        )
        assert b"protect_content" in request.content
        return httpx.Response(status, json=response())

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        result = TelegramAdapter(TOKEN, client).send_document(
            recipient="991", file=file, action_id=uuid4()
        )
    assert result.state == state and len(calls) == 1


def test_modified_checked_bytes_are_rejected_before_network():
    file = checked_file()
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("must not send"))
    ) as client:
        with pytest.raises(ValueError):
            TelegramAdapter(TOKEN, client).send_document(
                recipient="991", file=replace(file, content=b"changed"), action_id=uuid4()
            )
