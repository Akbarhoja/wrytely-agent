"""Bounded, read-only feasibility probe; no OAuth, persistence or automatic retry."""

import json
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, quote, unquote, urlsplit

import httpx
from pydantic import SecretStr

ROOT = "https://graph.microsoft.com/v1.0"
MAX_BYTES = 1024 * 1024


class ProbeBlocked(RuntimeError):
    """Controlled reason only; never retain a response, request, token or cursor."""

    def __init__(self, code: str, retry_after: int | None = None):
        super().__init__(code)
        self.retry_after = retry_after


@dataclass(frozen=True)
class ProbeResult:
    summary: dict
    # Opaque links are private checkpoints, unsuitable for logs or student output.
    next_link: str | None = field(default=None, repr=False)
    delta_link: str | None = field(default=None, repr=False)


def _cursor(value, path: str, kind: str | None = None) -> str:
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) <= 32 for c in value):
        raise ProbeBlocked("unsafe_cursor")
    try:
        url = urlsplit(value)
        params = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        raise ProbeBlocked("unsafe_cursor") from None
    keys = [key for key, _ in params]
    tokens = [key for key in keys if key in {"$skiptoken", "$deltatoken"}]
    if (
        url.scheme != "https"
        or url.netloc != "graph.microsoft.com"
        or unquote(url.path) != unquote(path)
        or url.fragment
        or len(tokens) != 1
        or (kind is not None and tokens != [kind])
        or len(set(keys)) != len(keys)
        or not set(keys) <= {"$skiptoken", "$deltatoken", "$select", "$top"}
        or any(not val for key, val in params if key in tokens)
    ):
        raise ProbeBlocked("unsafe_cursor")
    return value  # Preserve the opaque provider URL; do not reconstruct its token.


def _get(client: httpx.Client, token: SecretStr, url: str) -> dict:
    try:
        with client.stream(
            "GET",
            url,
            headers={
                "Authorization": f"Bearer {token.get_secret_value()}",
                "Accept": "application/json",
                "Prefer": 'IdType="ImmutableId", outlook.body-content-type="text"',
            },
            timeout=15,
            follow_redirects=False,
        ) as response:
            status = response.status_code
            if 300 <= status < 400:
                raise ProbeBlocked("redirect_blocked")
            if status != 200:
                code = {
                    401: "reconnect_required",
                    403: "consent_or_access_denied",
                    410: "delta_reset_required",
                    429: "rate_limited",
                    503: "provider_unavailable",
                }.get(status, "provider_error")
                retry = response.headers.get("Retry-After", "")
                retry_after = (
                    int(retry) if status == 429 and retry.isdecimal() and len(retry) <= 4 else None
                )
                raise ProbeBlocked(
                    code, retry_after if retry_after is not None and retry_after <= 3600 else None
                )
            if response.headers.get("content-type", "").split(";")[0].lower() != "application/json":
                raise ProbeBlocked("invalid_response")
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > MAX_BYTES:
                    raise ProbeBlocked("size_limit")
    except httpx.HTTPError:
        raise ProbeBlocked("network_failure") from None
    try:
        result = json.loads(content)
    except (ValueError, UnicodeError):
        raise ProbeBlocked("invalid_response") from None
    if not isinstance(result, dict):
        raise ProbeBlocked("invalid_response")
    return result


def _provider_id(value) -> str:
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ProbeBlocked("invalid_response")
    return value


def probe_inbox(
    client: httpx.Client,
    token: SecretStr,
    *,
    expected_subject: str,
    cursor: str | None = None,
    max_pages: int = 3,
) -> ProbeResult:
    """Check one consented Inbox; expected_subject comes from verified OAuth, not a browser ID.

    Caller owns credentials/client and must use a zero-retry transport, no HTTP debug
    logging and no provider calls without authorization. There are no import-time IO,
    token acquisition/refresh, app routes or shared-store consumers in this spike.
    """
    if (
        type(max_pages) is not int
        or not 1 <= max_pages <= 10
        or not isinstance(expected_subject, str)
        or not expected_subject
        or len(expected_subject) > 1024
        or not isinstance(token, SecretStr)
        or not token.get_secret_value()
    ):
        raise ProbeBlocked("invalid_probe_configuration")

    def identity():
        actual = _provider_id(_get(client, token, ROOT + "/me?$select=id").get("id"))
        if actual != expected_subject:
            raise ProbeBlocked("identity_mismatch")

    identity()
    folder = _provider_id(_get(client, token, ROOT + "/me/mailFolders/inbox?$select=id").get("id"))
    path = f"/v1.0/me/mailFolders/{quote(folder, safe='')}/messages/delta"
    next_url = (
        _cursor(cursor, path)
        if cursor is not None
        else "https://graph.microsoft.com"
        + path
        + "?$select=id,parentFolderId,subject,body,receivedDateTime,"
        + "lastModifiedDateTime,hasAttachments"
        + "&$top=25"
    )
    seen_urls: set[str] = set()
    seen_ids: set[str] = set()
    records = bodies = removed = 0
    final_url = None
    for _ in range(max_pages):
        if next_url in seen_urls:
            raise ProbeBlocked("cursor_cycle")
        seen_urls.add(next_url)
        page = _get(client, token, next_url)
        values = page.get("value")
        if not isinstance(values, list) or len(values) + records > 1000:
            raise ProbeBlocked("invalid_response")
        next_value, final_value = page.get("@odata.nextLink"), page.get("@odata.deltaLink")
        if bool(next_value) == bool(final_value):
            raise ProbeBlocked("invalid_response")
        next_url = _cursor(next_value, path, "$skiptoken") if next_value else None
        final_url = _cursor(final_value, path, "$deltatoken") if final_value else None
        for item in values:
            if not isinstance(item, dict):
                raise ProbeBlocked("invalid_response")
            seen_ids.add(_provider_id(item.get("id")))
            records += 1
            # A folder tombstone can mean a move, not confirmed mailbox deletion.
            if "@removed" in item:
                if not isinstance(item["@removed"], dict):
                    raise ProbeBlocked("invalid_response")
                removed += 1
            elif isinstance(item.get("body"), dict) and isinstance(
                item["body"].get("content"), str
            ):
                bodies += 1
        if next_url is None:
            break
    identity()  # Any mismatch/failure discards both counts and private checkpoint.
    return ProbeResult(
        summary={
            "state": "complete_round" if final_url else "partial_round",
            "pages": len(seen_urls),
            "records": records,
            "unique_ids": len(seen_ids),
            "body_records": bodies,
            "removed_from_folder_records": removed,
        },
        next_link=next_url,
        delta_link=final_url,
    )
