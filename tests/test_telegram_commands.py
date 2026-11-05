from uuid import uuid4

import pytest

from contracts.telegram_commands import parse_academic_command


@pytest.mark.parametrize("verb,kind", [("accept", "accept_offer"), ("decline", "decline_offer")])
def test_explicit_target_is_required_and_never_guessed(verb, kind):
    target = uuid4()
    command = parse_academic_command(f"/{verb} {target}")
    assert command.kind == kind and command.target_id == target
    assert command.instructions == ""


def test_revision_preserves_explicit_multiline_instructions():
    target = uuid4()
    command = parse_academic_command(
        f"/revise {target} Make the title clearer.\nKeep the citations."
    )
    assert command.kind == "revise_artifact" and command.target_id == target
    assert command.instructions == "Make the title clearer.\nKeep the citations."


def test_file_request_requires_an_explicit_artifact():
    target = uuid4()
    assert parse_academic_command(f"/file {target}").kind == "send_artifact"
    with pytest.raises(ValueError):
        parse_academic_command("/file latest")


@pytest.mark.parametrize(
    "text",
    [
        "/accept",
        "/decline latest",
        "/accept https://example.test",
        "/accept {12345678-1234-1234-1234-123456789012}",
        "/accept 12345678123412341234123456789012",
        "/accept 12345678-1234-1234-1234-123456789012 extra permission",
        "/revise 12345678-1234-1234-1234-123456789012",
        "/revise 12345678-1234-1234-1234-123456789012 " + "x" * 4001,
    ],
)
def test_malformed_recognized_commands_fail_closed(text):
    with pytest.raises(ValueError):
        parse_academic_command(text)


@pytest.mark.parametrize("text", ["/help", "/acceptance", "Please accept my offer"])
def test_unsupported_commands_and_natural_language_are_not_delegation(text):
    assert parse_academic_command(text) is None
