"""Fixed isolated parser entrypoint. Caps precede parser import and document IO."""

import json
import sys


def _apply_limits(limits):
    import resource

    for kind, requested in [
        (resource.RLIMIT_AS, limits["memory_bytes"]),
        (resource.RLIMIT_CPU, limits["cpu_seconds"]),
    ]:
        _, inherited = resource.getrlimit(kind)
        target = requested if inherited == resource.RLIM_INFINITY else min(inherited, requested)
        resource.setrlimit(kind, (target, target))
        effective = resource.getrlimit(kind)
        if any(value == resource.RLIM_INFINITY or value > requested for value in effective):
            raise ValueError("Unenforced resource cap")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _extract(data, limits):
    import io
    import logging
    import unicodedata

    logging.disable(logging.CRITICAL)
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        return {"status": "blocked", "reason": "encrypted"}
    count = len(reader.pages)
    if not 1 <= count <= limits["max_pages"]:
        return {"status": "blocked", "reason": "resource_limit"}
    pages = []
    size = count - 1
    reasons = {"pdf_text_only", "layout_unverified"}
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
        if not text.strip():
            text = ""
            reasons.add("empty_pages_or_unread_images")
        size += len(text)
        if size > limits["max_chars"]:
            return {"status": "blocked", "reason": "resource_limit"}
        pages.append({"page": number, "text": text})
    return {"status": "partial", "reasons": sorted(reasons), "pages": pages}


def main():
    try:
        limits = json.loads(sys.argv[1])
        if sys.platform != "linux":
            raise ValueError()
        _apply_limits(limits)
    except Exception:
        result = {"status": "blocked", "reason": "limits_unavailable"}
    else:
        try:
            data = sys.stdin.buffer.read(limits["max_input"] + 1)
            if len(data) > limits["max_input"]:
                result = {"status": "blocked", "reason": "resource_limit"}
            else:
                result = _extract(data, limits)
        except MemoryError:
            result = {"status": "blocked", "reason": "resource_limit"}
        except Exception:
            result = {"status": "blocked", "reason": "parse_failed"}
    try:
        encoded = json.dumps(result, ensure_ascii=False).encode("utf-8")
        if len(encoded) > 2 * 1024 * 1024:
            encoded = b'{"status":"blocked","reason":"resource_limit"}'
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
    except Exception:
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
