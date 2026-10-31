import io
import os
import sys
import time
from pathlib import Path

import pytest

from integrations.canvas.pdf_extract import PdfLimits, _decode, _supervise, extract_pdf

LINUX = pytest.mark.skipif(sys.platform != "linux", reason="Requires actual Linux OS caps/pipes")
CHILD = Path(__file__).resolve().parents[1] / "integrations/canvas/_pdf_child.py"


def document(texts, encrypted=False):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(200, 200)
        if text:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): writer._add_object(font)}
                    )
                }
            )
            stream = DecodedStreamObject()
            stream.set_data(b"BT /F1 12 Tf 10 100 Td (" + text.encode("ascii") + b") Tj ET")
            page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("synthetic-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_input": True},
        {"max_pages": 201},
        {"max_chars": 200001},
        {"cpu_seconds": 6},
        {"memory_bytes": 2**31},
        {"wall_seconds": 11},
        {"wall_seconds": float("nan")},
    ],
)
def test_pdf_limits_cannot_expand_or_accept_boolean(kwargs):
    with pytest.raises(ValueError):
        PdfLimits(**kwargs)


def test_supplied_bytes_only_and_input_limit():
    with pytest.raises(ValueError):
        extract_pdf("https://private.example/document.pdf")
    result = extract_pdf(b"x" * 10, limits=PdfLimits(max_input=9))
    assert result.status == "blocked" and result.reasons == ("input_limit",)
    assert result.pages == ()


def test_unsupported_platform_never_launches_or_parses(monkeypatch):
    import integrations.canvas.pdf_extract as module

    monkeypatch.setattr(module.sys, "platform", "win32")
    monkeypatch.setattr(module, "_supervise", lambda *a: pytest.fail("Must not start a child"))
    result = extract_pdf(b"%PDF-synthetic")
    assert result.reasons == ("unsupported_platform",)
    assert result.pages == ()


def test_child_does_not_inherit_caller_credentials(monkeypatch):
    import integrations.canvas.pdf_extract as module

    monkeypatch.setenv("WRYTELY_SYNTHETIC_PRIVATE_SENTINEL", "synthetic-value")
    captured = []

    def unavailable(*args, **kwargs):
        captured.append(kwargs.get("env"))
        raise OSError("Synthetic launch failure")

    monkeypatch.setattr(module.subprocess, "Popen", unavailable)
    result = _supervise([sys.executable], b"", PdfLimits())
    assert result.reason == "child_unavailable"
    assert captured[0] is not None
    assert "WRYTELY_SYNTHETIC_PRIVATE_SENTINEL" not in captured[0]


@LINUX
def test_real_pdf_text_and_page_provenance_remain_partial():
    result = extract_pdf(document(["First page", "Second page"]))
    assert result.status == "partial"
    assert [p.page for p in result.pages] == [1, 2]
    assert "First page" in result.pages[0].text
    assert "Second page" in result.pages[1].text
    assert "layout_unverified" in result.reasons
    assert "First page" not in repr(result)


@LINUX
@pytest.mark.parametrize(
    "data,reason", [(b"private-synthetic-invalid-pdf", "parse_failed"), (b"", "empty_input")]
)
def test_pdf_failure_has_no_private_prefix(data, reason):
    result = extract_pdf(data)
    assert result.status == "blocked" and reason in result.reasons
    assert result.pages == () and "private-synthetic" not in repr(result)


@LINUX
def test_encrypted_pdf_is_rejected_without_decryption():
    result = extract_pdf(document(["Secret synthetic text"], encrypted=True))
    assert result.reasons == ("encrypted",) and result.pages == ()


@LINUX
def test_empty_and_mixed_pages_remain_explicit_gaps():
    result = extract_pdf(document(["", "Readable synthetic text", ""]))
    assert result.status == "partial" and len(result.pages) == 3
    assert result.pages[0].text == result.pages[2].text == ""
    assert "empty_pages_or_unread_images" in result.reasons


@LINUX
def test_pdf_page_and_character_overflow_discards_all_text():
    for data, limits in [
        (document(["A", "B"]), PdfLimits(max_pages=1)),
        (document(["Synthetic long text"]), PdfLimits(max_chars=3)),
    ]:
        result = extract_pdf(data, limits=limits)
        assert result.status == "blocked" and result.pages == ()
        assert result.reasons == ("resource_limit",)


@LINUX
@pytest.mark.parametrize(
    "stream,reason,count",
    [("stdout", "stdout_limit", 2 * 1024 * 1024 + 1), ("stderr", "stderr_limit", 8193)],
)
def test_actual_child_output_pipes_are_bounded(stream, reason, count):
    script = f"import sys; sys.{stream}.buffer.write(b'x'*{count}); sys.{stream}.flush()"
    result = _supervise([sys.executable, "-I", "-c", script], b"", PdfLimits())
    assert result.reason == reason and result.data == b""
    with pytest.raises(ChildProcessError):
        os.waitpid(result.pid, os.WNOHANG)


@LINUX
def test_full_stdin_pipe_cannot_defeat_wall_timeout_or_reaping():
    started = time.monotonic()
    result = _supervise(
        [
            sys.executable,
            "-I",
            "-c",
            "import time; print('private-prefix',flush=True); time.sleep(30)",
        ],
        b"x" * 1024 * 1024,
        PdfLimits(wall_seconds=0.15),
    )
    assert result.reason == "timeout" and result.data == b""
    assert time.monotonic() - started < 3
    with pytest.raises(ChildProcessError):
        os.waitpid(result.pid, os.WNOHANG)


def cap_script(body):
    return (
        "import importlib.util; "
        f"s=importlib.util.spec_from_file_location('pdf_cap_test',{str(CHILD)!r}); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "m._apply_limits({'memory_bytes':67108864,'cpu_seconds':1}); " + body
    )


@LINUX
def test_actual_linux_memory_cap_is_enforced():
    script = cap_script(
        "\ntry: bytearray(134217728)\nexcept MemoryError: raise SystemExit(71)"
        "\nraise SystemExit(72)"
    )
    result = _supervise([sys.executable, "-I", "-c", script], b"", PdfLimits())
    assert result.returncode == 71 and result.data == b""


@LINUX
def test_actual_linux_cpu_cap_is_enforced():
    script = cap_script("\nwhile True: pass")
    result = _supervise([sys.executable, "-I", "-c", script], b"", PdfLimits())
    assert result.returncode < 0 and result.reason == "child_failed"
    with pytest.raises(ChildProcessError):
        os.waitpid(result.pid, os.WNOHANG)


@LINUX
def test_one_child_limit_is_enforced(monkeypatch):
    import integrations.canvas.pdf_extract as module

    assert module._SLOTS.acquire(blocking=False)
    try:
        result = extract_pdf(b"%PDF-synthetic")
        assert result.reasons == ("busy",)
    finally:
        module._SLOTS.release()


@pytest.mark.parametrize(
    "data",
    [
        b"private-prefix",
        b"[]",
        b'{"status":"complete"}',
        b'{"status":"partial","reasons":["layout_unverified","pdf_text_only"],"pages":[{"page":1,"text":"\\ud800"}]}',
        b'{"status":"partial","reasons":["layout_unverified","pdf_text_only"],"pages":[{"page":1,"text":"e\\u0301"}]}',
        b'{"status":"partial","reasons":["layout_unverified","pdf_text_only"],"pages":[{"page":2,"text":"A"}]}',
    ],
)
def test_invalid_or_unnormalized_child_output_never_becomes_text(data):
    result = _decode(data, PdfLimits())
    assert result.status == "blocked" and result.pages == ()
    assert result.reasons == ("invalid_child_output",)
    assert "private-prefix" not in repr(result)


def test_normalized_unicode_output_bound_is_checked_again_by_parent():
    import json

    data = json.dumps(
        {
            "status": "partial",
            "reasons": ["layout_unverified", "pdf_text_only"],
            "pages": [{"page": 1, "text": "\u0308\u0301"}],
        }
    ).encode()
    assert _decode(data, PdfLimits(max_chars=1)).pages == ()
    result = _decode(data, PdfLimits(max_chars=2))
    assert result.pages[0].text == "\u0308\u0301"


@LINUX
def test_missing_effective_caps_prevent_parser_import():
    import json

    script = (
        "import importlib.util,resource,sys,json; "
        f"s=importlib.util.spec_from_file_location('cap_test',{str(CHILD)!r}); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "resource.setrlimit=lambda *a: None; resource.getrlimit=lambda *a: (-1,-1); "
        "sys.argv=['worker',json.dumps({'memory_bytes':67108864,'cpu_seconds':1})]; "
        "m.main(); assert 'pypdf' not in sys.modules"
    )
    result = _supervise([sys.executable, "-I", "-c", script], b"private-pdf", PdfLimits())
    assert result.returncode == 0
    assert json.loads(result.data) == {"status": "blocked", "reason": "limits_unavailable"}


@LINUX
def test_image_only_pdf_has_no_invented_text():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

    writer = PdfWriter()
    page = writer.add_blank_page(200, 200)
    image = DecodedStreamObject()
    image.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(1),
            NameObject("/Height"): NumberObject(1),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8),
        }
    )
    image.set_data(b"\x00\x00\x00")
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/XObject"): DictionaryObject({NameObject("/Im0"): writer._add_object(image)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"q 100 0 0 100 0 0 cm /Im0 Do Q")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    result = extract_pdf(output.getvalue())
    assert result.status == "partial" and result.pages[0].text == ""
    assert "empty_pages_or_unread_images" in result.reasons
