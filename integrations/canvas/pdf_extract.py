"""Bytes-only partial PDF preparation. No parser is imported in the caller."""

import json
import math
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

_STDOUT = 2 * 1024 * 1024
_STDERR = 8192
_SLOTS = threading.BoundedSemaphore(1)
_REASONS = {"encrypted", "parse_failed", "resource_limit", "limits_unavailable", "empty_input"}


@dataclass(frozen=True)
class PdfLimits:
    max_input: int = 10 * 1024 * 1024
    max_pages: int = 200
    max_chars: int = 200000
    memory_bytes: int = 1024 * 1024 * 1024
    cpu_seconds: int = 5
    wall_seconds: float = 10

    def __post_init__(self):
        for name, low, high in [
            ("max_input", 1, 10 * 1024 * 1024),
            ("max_pages", 1, 200),
            ("max_chars", 1, 200000),
            ("memory_bytes", 64 * 1024 * 1024, 1024**3),
            ("cpu_seconds", 1, 5),
        ]:
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError("Invalid PDF limits")
        if (
            type(self.wall_seconds) not in (int, float)
            or not math.isfinite(self.wall_seconds)
            or not 0.05 <= self.wall_seconds <= 10
        ):
            raise ValueError("Invalid PDF limits")


@dataclass(frozen=True)
class PdfPage:
    page: int
    text: str = field(repr=False)


@dataclass(frozen=True)
class PdfExtraction:
    status: str
    reasons: tuple[str, ...]
    pages: tuple[PdfPage, ...] = field(default=(), repr=False)


@dataclass(frozen=True)
class _WireOutput:
    reason: str
    returncode: int | None
    pid: int | None
    data: bytes = field(default=b"", repr=False)


def _supervise(command, data, limits):
    """Internal fixed-command supervisor; public callers supply bytes, never commands."""
    process = None
    output = bytearray()
    error_size = sent = 0
    reason = ""
    deadline = time.monotonic() + limits.wall_seconds
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            start_new_session=True,
            env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
        with selectors.DefaultSelector() as selector:
            for stream, role in [
                (process.stdin, "input"),
                (process.stdout, "output"),
                (process.stderr, "error"),
            ]:
                os.set_blocking(stream.fileno(), False)
                selector.register(
                    stream, selectors.EVENT_WRITE if role == "input" else selectors.EVENT_READ, role
                )
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    reason = "timeout"
                    break
                for key, _ in selector.select(min(remaining, 0.1)):
                    stream = key.fileobj
                    if key.data == "input":
                        try:
                            sent += (
                                os.write(stream.fileno(), memoryview(data)[sent : sent + 65536])
                                if sent < len(data)
                                else 0
                            )
                        except BrokenPipeError:
                            sent = len(data)
                        except BlockingIOError:
                            continue
                        if sent == len(data):
                            selector.unregister(stream)
                            stream.close()
                    else:
                        try:
                            chunk = os.read(stream.fileno(), 65536)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            selector.unregister(stream)
                            stream.close()
                        elif key.data == "output":
                            if len(output) + len(chunk) > _STDOUT:
                                reason = "stdout_limit"
                                break
                            output.extend(chunk)
                        else:
                            error_size += len(chunk)
                            if error_size > _STDERR:
                                reason = "stderr_limit"
                                break
                if reason:
                    break
        if not reason:
            try:
                process.wait(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                reason = "timeout"
    except (OSError, ValueError):
        reason = "child_unavailable"
    finally:
        if process is not None:
            if reason:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                if not stream.closed:
                    stream.close()
    if process is None:
        return _WireOutput(reason, None, None)
    reason = reason or ("child_failed" if process.returncode else "")
    return _WireOutput(
        reason, process.returncode, process.pid, bytes(output) if not reason else b""
    )


def _decode(data, limits):
    try:
        value = json.loads(data)
        if (
            value.keys() == {"status", "reason"}
            and value["status"] == "blocked"
            and value["reason"] in _REASONS
        ):
            return PdfExtraction("blocked", (value["reason"],))
        if value.keys() != {"status", "reasons", "pages"} or value["status"] != "partial":
            raise ValueError()
        reasons = value["reasons"]
        if (
            not isinstance(reasons, list)
            or reasons != sorted(set(reasons))
            or not {"pdf_text_only", "layout_unverified"} <= set(reasons)
            or set(reasons) - {"pdf_text_only", "layout_unverified", "empty_pages_or_unread_images"}
        ):
            raise ValueError()
        rows = value["pages"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= limits.max_pages:
            raise ValueError()
        pages = []
        size = len(rows) - 1
        for number, row in enumerate(rows, 1):
            if (
                row.keys() != {"page", "text"}
                or type(row["page"]) is not int
                or row["page"] != number
                or not isinstance(row["text"], str)
            ):
                raise ValueError()
            text = row["text"]
            text.encode("utf-8")
            if unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n")) != text:
                raise ValueError()
            size += len(text)
            if size > limits.max_chars:
                raise ValueError()
            pages.append(PdfPage(number, text))
        if (
            any(not page.text.strip() for page in pages)
            and "empty_pages_or_unread_images" not in reasons
        ):
            raise ValueError()
        return PdfExtraction("partial", tuple(reasons), tuple(pages))
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return PdfExtraction("blocked", ("invalid_child_output",))


def extract_pdf(data, *, limits=None):
    """Return private partial page text or a controlled failure, never a failed prefix."""
    if type(data) is not bytes:
        raise ValueError("Supplied PDF bytes required")
    limits = PdfLimits() if limits is None else limits
    if type(limits) is not PdfLimits:
        raise ValueError("Invalid PDF limits")
    if not data:
        return PdfExtraction("blocked", ("empty_input",))
    if len(data) > limits.max_input:
        return PdfExtraction("blocked", ("input_limit",))
    if sys.platform != "linux":
        return PdfExtraction("blocked", ("unsupported_platform",))
    if not _SLOTS.acquire(blocking=False):
        return PdfExtraction("blocked", ("busy",))
    try:
        child = Path(__file__).with_name("_pdf_child.py")
        result = _supervise(
            [sys.executable, "-I", str(child), json.dumps(asdict(limits))], data, limits
        )
        if result.reason:
            return PdfExtraction("blocked", (result.reason,))
        return _decode(result.data, limits)
    finally:
        _SLOTS.release()
