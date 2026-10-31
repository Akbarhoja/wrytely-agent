"""Inert, bounded text preparation; never certifies complete Canvas coverage."""

import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal

CEILINGS = (1048576, 200000, 20000, 128)
VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
OMIT = frozenset(
    "script style head template noscript iframe object embed svg math canvas video audio".split()
)
BLOCK = frozenset(
    "address article aside blockquote div dl dt dd fieldset figcaption figure footer form "
    "h1 h2 h3 h4 h5 h6 header hr li main nav ol p pre section table tr ul".split()
)


@dataclass(frozen=True)
class HtmlExtraction:
    text: str
    status: Literal["partial", "blocked"]
    reasons: tuple[str, ...]


class _Blocked(Exception):
    pass


class _Text(HTMLParser):
    def __init__(self, max_chars, max_events, max_depth):
        super().__init__(convert_charrefs=True)
        self.max_chars, self.max_events, self.max_depth = max_chars, max_events, max_depth
        self.events = self.chars = 0
        self.stack = []
        self.parts = []
        self.reasons = {"html_text_only"}

    def event(self):
        self.events += 1
        if self.events > self.max_events:
            raise _Blocked("resource_limit")

    def append(self, value):
        self.chars += len(value)
        if self.chars > self.max_chars:
            raise _Blocked("resource_limit")
        self.parts.append(value)

    def handle_starttag(self, tag, attrs):
        self.event()
        if len({name for name, _ in attrs}) != len(attrs):
            raise _Blocked("malformed_markup")
        attrs = dict(attrs)
        style = re.sub(r"\s+", "", attrs.get("style") or "").lower()
        hidden = (
            "hidden" in attrs
            or (attrs.get("aria-hidden") or "").lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
        )
        omitted = hidden or tag in OMIT
        if hidden:
            self.reasons.add("hidden_content_omitted")
        if tag in OMIT or tag in {"img", "input"}:
            self.reasons.add("nontext_content_unread")
        if tag == "a" and attrs.get("href") and not attrs["href"].startswith("#"):
            self.reasons.add("linked_content_unread")
        suppressed = omitted or bool(self.stack and self.stack[-1][1])
        if not suppressed:
            if tag in BLOCK or tag == "br":
                self.append("\n")
            elif tag in {"td", "th"}:
                self.append(" ")
        if tag not in VOID:
            if len(self.stack) >= self.max_depth:
                raise _Blocked("resource_limit")
            self.stack.append((tag, suppressed))

    def handle_endtag(self, tag):
        self.event()
        if tag in VOID:
            return
        if not self.stack or self.stack[-1][0] != tag:
            raise _Blocked("malformed_markup")
        _, suppressed = self.stack.pop()
        if not suppressed and tag in BLOCK:
            self.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag not in VOID:
            raise _Blocked("malformed_markup")
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        self.event()
        if not self.stack or not self.stack[-1][1]:
            self.append(data)

    def handle_comment(self, data):
        self.event()

    def handle_decl(self, decl):
        self.event()

    def handle_pi(self, data):
        self.event()

    def unknown_decl(self, data):
        raise _Blocked("malformed_markup")

    def parse_html_declaration(self, i):
        # Python 3.14 routes unknown declarations through bogus-comment handling.
        if not (
            self.rawdata.startswith("<!--", i) or self.rawdata[i : i + 9].lower() == "<!doctype"
        ):
            raise _Blocked("malformed_markup")
        return super().parse_html_declaration(i)


def extract_html(
    content: bytes, *, max_bytes=1048576, max_chars=200000, max_events=20000, max_depth=128
) -> HtmlExtraction:
    """Parse supplied UTF-8 bytes. Limits can only lower fixed ceilings; no IO/logging."""
    limits = (max_bytes, max_chars, max_events, max_depth)
    if any(
        type(n) is not int or not 1 <= n <= cap for n, cap in zip(limits, CEILINGS, strict=True)
    ):
        return HtmlExtraction("", "blocked", ("invalid_limits",))
    if not isinstance(content, bytes):
        return HtmlExtraction("", "blocked", ("invalid_input",))
    if len(content) > max_bytes:
        return HtmlExtraction("", "blocked", ("resource_limit",))
    try:
        source = content.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        return HtmlExtraction("", "blocked", ("invalid_encoding",))
    if any(ord(c) < 32 and c not in "\t\r\n" for c in source):
        return HtmlExtraction("", "blocked", ("invalid_encoding",))
    parser = _Text(max_chars, max_events, max_depth)
    try:
        parser.feed(source)
        parser.close()
    except _Blocked as exc:
        return HtmlExtraction("", "blocked", (str(exc),))
    if parser.stack:
        parser.reasons.add("unclosed_markup")
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    text = unicodedata.normalize("NFC", "\n".join(line for line in lines if line))
    if len(text) > max_chars:
        return HtmlExtraction("", "blocked", ("resource_limit",))
    if not text:
        return HtmlExtraction("", "blocked", ("no_text",))
    return HtmlExtraction(text, "partial", tuple(sorted(parser.reasons)))
