"""Bounded isolated PDF text extraction. No networking, rendering or embedded code."""

import json
import subprocess
import sys
import time

MAX_BYTES = 5 * 1024 * 1024


def extract_pdf(content):
    if type(content) is not bytes or len(content) > MAX_BYTES or not content.startswith(b"%PDF-"):
        return {"pages": [], "missing": ["invalid_or_oversized_pdf"]}
    process = subprocess.Popen(
        [sys.executable, "-m", "integrations.canvas.pdf_extract"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={"PATH": "", "PYTHONIOENCODING": "utf-8"},
    )
    deadline = time.monotonic() + 12
    first = True
    while True:
        try:
            output, _ = process.communicate(content if first else None, timeout=0.1)
            break
        except subprocess.TimeoutExpired:
            first = False
            over_memory = False
            if sys.platform == "darwin":
                try:
                    used = subprocess.run(
                        ["/bin/ps", "-o", "rss=", "-p", str(process.pid)],
                        capture_output=True,
                        timeout=1,
                        check=True,
                    )
                    over_memory = int(used.stdout.strip()) > 512 * 1024
                except Exception:
                    over_memory = process.poll() is None
            if time.monotonic() >= deadline or over_memory:
                process.kill()
                process.communicate()
                return {"pages": [], "missing": ["pdf_extraction_limit"]}
    if process.returncode or len(output) > 2 * 1024 * 1024:
        return {"pages": [], "missing": ["pdf_extraction_failed"]}
    try:
        result = json.loads(output)
        if (
            type(result) is not dict
            or result.keys() != {"pages", "missing"}
            or type(result["pages"]) is not list
            or len(result["pages"]) > 200
            or any(type(x) is not str for x in result["pages"])
            or sum(map(len, result["pages"])) > 200000
        ):
            raise ValueError()
        return result
    except (ValueError, TypeError):
        return {"pages": [], "missing": ["pdf_extraction_failed"]}


def _child():
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    import io
    import unicodedata

    from pypdf import PdfReader, overwrite_configuration

    overwrite_configuration(
        maximum_declared_stream_length=16000000,
        zlib_maximum_output_length=16000000,
        lzw_maximum_output_length=16000000,
        array_based_stream_maximum_output_length=16000000,
        run_length_maximum_output_length=16000000,
        stream_decoding_work_maximum_length=32000000,
        page_tree_maximum_entries=5000,
        jbig2dec_binary=None,
        disable_legacy_handling=True,
    )
    data = sys.stdin.buffer.read(MAX_BYTES + 1)
    result = {"pages": [], "missing": ["pdf_text_only", "pdf_layout_and_images_unread"]}
    try:
        if len(data) > MAX_BYTES or not data.startswith(b"%PDF-"):
            raise ValueError()
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 200:
            raise ValueError()
        total = 0
        for page in reader.pages:
            value = unicodedata.normalize(
                "NFC", (page.extract_text() or "").replace("\r\n", "\n").replace("\r", "\n")
            )
            if "\x00" in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
                raise ValueError()
            total += len(value) + 1
            if total > 200000:
                raise ValueError()
            result["pages"].append(value)
        if any(not p.strip() for p in result["pages"]):
            result["missing"].append("pdf_page_text_unread")
    except Exception:
        result = {"pages": [], "missing": ["pdf_extraction_failed"]}
    sys.stdout.write(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    _child()
