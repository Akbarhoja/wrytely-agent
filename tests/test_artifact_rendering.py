"""Private checked-file output: exact text, inert XML and final authority check."""

import hashlib
import io
from copy import deepcopy
from uuid import uuid4
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from test_canvas_sync import device as device

from runtime.artifact_rendering import ArtifactNotReady, render_private_artifact_docx
from shared.canvas_reads import SourceRefreshRequired


def detail():
    return dict(
        schema_version=2,
        artifact=dict(
            id=str(uuid4()),
            memory_revision=1,
            saved_state="ready",
            memory_stale=False,
            draft=dict(
                schema_version=2,
                title="Course study draft",
                body="First < & >\nCafé 📚",
                disclosure="Prepared with AI assistance.",
                citations=[],
            ),
        ),
        latest_check=dict(id=str(uuid4()), report=dict(passed=True)),
        evidence_status=dict(state="current"),
        controls=dict(agent_paused=False, responsibility_status="active"),
    )


class Reader:
    def __init__(self, data, changed=None):
        self.data, self.changed, self.calls = data, changed, 0

    def read_private_artifact_v2(self, user, artifact):
        assert user == "verified-owner" and artifact == self.data["artifact"]["id"]
        self.calls += 1
        return deepcopy(self.changed if self.calls > 1 and self.changed else self.data)


def render(reader):
    return render_private_artifact_docx(reader, "verified-owner", reader.data["artifact"]["id"])


def test_docx_is_deterministic_inert_and_preserves_unicode_and_disclosure():
    reader = Reader(detail())
    a, b = render(reader), render(reader)
    assert a.content == b.content and a.sha256 == hashlib.sha256(a.content).hexdigest()
    with ZipFile(io.BytesIO(a.content)) as archive:
        assert set(archive.namelist()) == {
            "[Content_Types].xml",
            "_rels/.rels",
            "word/document.xml",
        }
        root = ET.fromstring(archive.read("word/document.xml"))
        text = "\n".join(root.itertext())
        assert "First < & >" in text and "Café 📚" in text
        assert "Prepared with AI assistance." in text
        assert b'TargetMode="External"' not in archive.read("_rels/.rels")


@pytest.mark.parametrize("state", ["unverified", "historical", "stale", "incomplete"])
def test_noncurrent_evidence_cannot_be_exported_as_checked(state):
    data = detail()
    data["evidence_status"]["state"] = state
    with pytest.raises(ArtifactNotReady):
        render(Reader(data))


@pytest.mark.parametrize("change", ["pause", "failed_check", "source_changed", "draft_changed"])
def test_control_or_content_change_during_render_prevents_return(change):
    data = detail()
    after = deepcopy(data)
    if change == "pause":
        after["controls"]["agent_paused"] = True
    elif change == "failed_check":
        after["latest_check"]["report"]["passed"] = False
    elif change == "source_changed":
        after["artifact"]["memory_stale"] = True
    else:
        after["artifact"]["draft"]["body"] = "Different version"
    with pytest.raises((ArtifactNotReady, SourceRefreshRequired)):
        render(Reader(data, after))


@pytest.mark.parametrize("body", [r"$$x^2$$", r"\frac{1}{2}", "invalid\x01text"])
def test_unsupported_equations_and_xml_characters_are_explicit(body):
    data = detail()
    data["artifact"]["draft"]["body"] = body
    with pytest.raises(ValueError):
        render(Reader(data))


def test_real_private_store_export_denies_other_student(device):
    from test_private_artifact_reads import ready

    _, saved = ready(device)
    db = device[0]
    result = render_private_artifact_docx(db, "user_alice", saved["id"])
    assert result.artifact_id == str(saved["id"]) and result.content.startswith(b"PK")
    db.provision("user_bob")
    with pytest.raises(LookupError):
        render_private_artifact_docx(db, "user_bob", saved["id"])
