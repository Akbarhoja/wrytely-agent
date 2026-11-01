"""Internal v2 evidence preserves distinct identities and strict original offsets."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from contracts.document_artifacts import (
    CoursePolicyV2,
    DocumentEvidence,
    DraftArtifactV2,
    LegacyEvidence,
)


def document():
    return dict(
        kind="canvas_document",
        object_id=str(uuid4()),
        observation_id=str(uuid4()),
        document_version_id=str(uuid4()),
        segment_id=str(uuid4()),
        slot=0,
        page=None,
        start=10,
        end=16,
        quote="Café 📚",
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("slot", True),
        ("slot", 512),
        ("slot", "0"),
        ("page", True),
        ("page", 0),
        ("page", 201),
        ("start", -1),
        ("end", 15),
        ("quote", "Cafe\u0301 📚"),
        ("quote", "\ud800"),
        ("quote", ""),
        ("segment_id", "invalid"),
        ("object_id", True),
    ],
)
def test_document_fields_reject_coercion_bad_identity_and_noncanonical_quote(key, value):
    with pytest.raises(ValidationError):
        DocumentEvidence.model_validate(document() | {key: value})


def test_document_reference_does_not_masquerade_as_a_legacy_version():
    ref = DocumentEvidence.model_validate(document())
    assert not hasattr(ref, "version_id")
    assert ref.end - ref.start == len(ref.quote)
    with pytest.raises(ValidationError):
        LegacyEvidence.model_validate(ref.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        DocumentEvidence.model_validate(ref.model_dump(mode="json") | {"version_id": str(uuid4())})


def test_typed_policy_discriminator_is_required_and_unknown_kinds_are_rejected():
    data = document()
    data.pop("kind")
    with pytest.raises(ValidationError):
        CoursePolicyV2(status="permitted", evidence=data)
    with pytest.raises(ValidationError):
        CoursePolicyV2(status="permitted", evidence=document() | {"kind": "browser"})


def test_internal_draft_schema_requires_explicit_version_and_preserves_mixed_refs():
    payload = dict(
        schema_version=2,
        title="Draft",
        body="A claim",
        disclosure="",
        citations=[
            dict(claim="A claim", evidence=document()),
            dict(
                claim="A claim", evidence=dict(kind="legacy", version_id=str(uuid4()), quote="fact")
            ),
        ],
    )
    draft = DraftArtifactV2.model_validate(payload)
    assert [c.evidence.kind for c in draft.citations] == ["canvas_document", "legacy"]
    del payload["schema_version"]
    with pytest.raises(ValidationError):
        DraftArtifactV2.model_validate(payload)
