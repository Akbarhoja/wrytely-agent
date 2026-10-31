"""Executable reference for the proposed C2 digest, not an ingestion API.

Provider adapters must map observations into this envelope first. Identity,
timestamps of collection, credentials and replay authorization are separate.
"""

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime

_KEYS = {"digest_version", "kind", "title", "content", "fields", "coverage", "missing"}
_DATES = {"due_at", "unlock_at", "lock_at", "submitted_at", "sent_at"}
_COVERAGE = {"complete", "partial", "restricted", "unsupported"}


def _text(value):
    normalized = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    # Reject invalid Unicode rather than letting encoders disagree on lone surrogates.
    normalized.encode("utf-8")
    return normalized


def _normalize(value, depth=0):
    if depth > 16:
        raise ValueError("Digest nesting limit")
    if type(value) is int and abs(value) > 2**53 - 1:
        raise ValueError("Digest integer exceeds interoperable range")
    if value is None or type(value) in (bool, int):
        return value
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, list):
        return [_normalize(item, depth + 1) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Digest keys must be strings")
            key = _text(key)
            if key in result:
                raise ValueError("Normalized digest key collision")
            if key in _DATES and item is not None:
                if not isinstance(item, str) or not re.fullmatch(
                    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
                    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])",
                    item,
                ):
                    raise ValueError("Digest dates must be timezone-aware RFC3339")
                item = datetime.fromisoformat(item.replace("Z", "+00:00"))
                item = (
                    item.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
                )
            result[key] = _normalize(item, depth + 1)
        return result
    raise ValueError("Digest accepts JSON integers, strings, booleans, lists, objects and null")


def canonical_source_bytes(payload: dict) -> bytes:
    """Return proposed v1 canonical UTF-8; rejects metadata and floating point."""
    if not isinstance(payload, dict) or payload.keys() != _KEYS:
        raise ValueError("Exact digest envelope required")
    if type(payload["digest_version"]) is not int or payload["digest_version"] != 1:
        raise ValueError("Unsupported digest version")
    for key in ("kind", "title", "content", "coverage"):
        if not isinstance(payload[key], str):
            raise ValueError("Digest text fields must be strings")
    if not payload["kind"] or payload["coverage"] not in _COVERAGE:
        raise ValueError("Invalid digest kind or coverage")
    if not isinstance(payload["fields"], dict):
        raise ValueError("Digest fields must be an object")
    missing = payload["missing"]
    if not isinstance(missing, list) or any(not isinstance(item, str) for item in missing):
        raise ValueError("Digest missing must be a string list")
    normalized = _normalize(payload)
    normalized["missing"] = sorted(set(normalized["missing"]))
    encoded = json.dumps(
        normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    if len(encoded) > 1024 * 1024:
        raise ValueError("Digest size limit")
    return encoded


def source_digest(payload: dict) -> str:
    return hashlib.sha256(canonical_source_bytes(payload)).hexdigest()
