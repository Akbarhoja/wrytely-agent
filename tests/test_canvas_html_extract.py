import pytest

from integrations.canvas.html_extract import extract_html


def test_structure_entities_and_unicode_stay_readable():
    result = extract_html(
        (
            "<h1>Cafe\u0301 &amp; tea</h1><p>One<br>two</p>"
            "<table><tr><td>A</td><td>B</td></tr></table>"
        ).encode()
    )
    assert result.text == "Café & tea\nOne\ntwo\nA B"
    assert result.status == "partial"
    assert "html_text_only" in result.reasons


@pytest.mark.parametrize(
    "tag",
    [
        "script",
        "style",
        "head",
        "template",
        "noscript",
        "iframe",
        "object",
        "svg",
        "math",
        "canvas",
        "video",
        "audio",
    ],
)
def test_active_embedded_and_nontext_subtrees_are_unread(tag):
    result = extract_html(
        f"<p>Before</p><{tag}><b>PRIVATE_OMITTED</b></{tag}><p>After</p>".encode()
    )
    assert result.text == "Before\nAfter"
    assert result.status == "partial"
    assert "nontext_content_unread" in result.reasons


@pytest.mark.parametrize(
    "attribute",
    [
        "hidden",
        'hidden="false"',
        'aria-hidden="true"',
        'style="display: none"',
        'style="visibility: hidden!important"',
    ],
)
def test_explicit_hidden_subtrees_do_not_leak(attribute):
    result = extract_html(
        f"<p>Visible</p><div {attribute}><span>PRIVATE_OMITTED</span></div>".encode()
    )
    assert result.text == "Visible"
    assert "hidden_content_omitted" in result.reasons


def test_links_images_and_breaks_do_not_silently_become_complete():
    result = extract_html(
        b'<p>Read <a href="https://private.invalid/secret">instructions</a>.</p>'
        b'<img alt="Chart" src="private"><hr><p>Next</p>'
    )
    assert result.text == "Read instructions.\nNext"
    assert {"linked_content_unread", "nontext_content_unread"} <= set(result.reasons)
    assert "private" not in result.text


@pytest.mark.parametrize("body", [b"", b"  ", b"<script>PRIVATE</script>", b"<!--PRIVATE-->"])
def test_no_text_is_blocked(body):
    result = extract_html(body)
    assert result.status == "blocked" and result.text == ""
    assert "no_text" in result.reasons


@pytest.mark.parametrize("body", [b"\xffPRIVATE", b"PRIVATE\x00", b"PRIVATE\x01", "PRIVATE", None])
def test_invalid_inputs_are_controlled_and_do_not_echo(body):
    result = extract_html(body)
    assert result.status == "blocked" and result.text == ""
    assert "PRIVATE" not in repr(result)


def test_mismatched_hidden_markup_is_blocked_without_partial_leak():
    result = extract_html(b"<p>Safe</p><div hidden><span>PRIVATE</div>PRIVATE</span>")
    assert result.status == "blocked" and result.text == ""
    assert "malformed_markup" in result.reasons


def test_unclosed_markup_is_explicitly_partial():
    result = extract_html(b"<p>Visible")
    assert result.text == "Visible" and result.status == "partial"
    assert "unclosed_markup" in result.reasons


@pytest.mark.parametrize(
    "kwargs,body",
    [
        ({"max_bytes": 3}, b"four"),
        ({"max_chars": 3}, b"four"),
        ({"max_chars": 2}, b"&#65;&#66;&#67;"),
        ({"max_events": 2}, b"<p>one</p>"),
        ({"max_depth": 1}, b"<div><p>one</p></div>"),
    ],
)
def test_limits_block_whole_result_instead_of_truncating(kwargs, body):
    result = extract_html(body, **kwargs)
    assert result.status == "blocked" and result.text == ""
    assert result.reasons == ("resource_limit",)


@pytest.mark.parametrize(
    "kwargs", [{"max_chars": 0}, {"max_bytes": 1048577}, {"max_depth": True}, {"max_events": -1}]
)
def test_limits_cannot_disable_or_expand_bounds(kwargs):
    assert extract_html(b"text", **kwargs).reasons == ("invalid_limits",)


def test_exact_input_and_output_limits_are_accepted():
    result = extract_html(b"abcd", max_bytes=4, max_chars=4, max_events=1)
    assert result.text == "abcd" and result.status == "partial"


@pytest.mark.parametrize(
    "body",
    [
        b"<script/>PRIVATE",
        b"<div/>PRIVATE",
        b'<div style="display:none" style="">PRIVATE</div>',
        b"<![PRIVATE]>",
        b"<p>Safe</p><![PRIVATE]>",
    ],
)
def test_ambiguous_markup_never_returns_hidden_text_or_parser_details(body):
    result = extract_html(body)
    assert result.text == "" and result.status == "blocked"
    assert result.reasons == ("malformed_markup",)
