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


@pytest.mark.parametrize(
    "source,expected",
    [
        (b"Plain instructions.", "Plain instructions."),
        (
            b"<h2>Task</h2><p>Explain <strong>three</strong> steps.<br>Use examples.</p>",
            "Task\nExplain three steps.\nUse examples.",
        ),
        ("<p>Cafe\u0301 &amp; tea</p>".encode(), "Café & tea"),
    ],
)
def test_v2_only_certifies_supplied_literal_text_and_leaves_v1_partial(source, expected):
    from integrations.canvas.html_extract import extract_html_v2

    result = extract_html_v2(source)
    assert result.text == expected
    assert result.status == "complete" and result.reasons == ()
    legacy = extract_html(source)
    assert legacy.status == "partial" and "html_text_only" in legacy.reasons


@pytest.mark.parametrize(
    "source",
    [
        b'<p>Read <a href="/files/1">attachment</a></p>',
        b'<p>Read</p><img src="/private" alt="Required chart">',
        b"<p hidden>Secret</p><p>Read</p>",
        b'<p class="hidden-by-external-css">Read</p>',
        b'<p style="color:red">Read</p>',
        b"<p>Read</p><script>PRIVATE</script>",
        b'<p>Read</p><iframe src="private"></iframe>',
        b"<pre>  preserve indentation\n    required</pre>",
        b"<code>a  b</code>",
        b"<table><tr><td>value</td></tr></table>",
        b'<ol start="4"><li>Required item</li></ol>',
        b"<p><del>old requirement</del>new requirement</p>",
        b"<p>e<sup>x</sup></p>",
        b"<custom>Read</custom>",
        b"<p>Read",
        b"<!doctype html><p>Read</p>",
        b"<!-- conditional content --><p>Read</p>",
        b"<p>Read &#0;</p>",
        b"<p>Read &#x41;</p>",
    ],
)
def test_v2_unread_structure_or_normalization_never_becomes_complete(source):
    from integrations.canvas.html_extract import extract_html_v2

    result = extract_html_v2(source)
    assert result.status != "complete" and result.reasons
    assert "PRIVATE" not in result.text


@pytest.mark.parametrize(
    "source", [b"<div hidden><p>PRIVATE</div></p>", b"\xff", b"", b"<p/>PRIVATE"]
)
def test_v2_malformed_and_empty_content_is_blocked(source):
    from integrations.canvas.html_extract import extract_html_v2

    result = extract_html_v2(source)
    assert result.status == "blocked" and result.text == "" and result.reasons


def test_v2_preserves_original_hard_bounds():
    from integrations.canvas.html_extract import extract_html_v2

    assert extract_html_v2(b"<p>long</p>", max_chars=2).reasons == ("resource_limit",)
    assert extract_html_v2(b"text", max_bytes=1048577).reasons == ("invalid_limits",)
