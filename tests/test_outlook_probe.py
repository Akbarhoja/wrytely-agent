import httpx
import pytest
from pydantic import SecretStr

from integrations.outlook.read_probe import ProbeBlocked, probe_inbox

ROOT = "https://graph.microsoft.com/v1.0"
DELTA = ROOT + "/me/mailFolders/folder-fixture/messages/delta"
TOKEN = SecretStr("synthetic-local-fixture")


def run(handler, **kwargs):
    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        return probe_inbox(client, TOKEN, expected_subject="subject-fixture", **kwargs)


def fixture(pages, *, switch=False):
    identities = 0
    calls = []

    def handle(request):
        nonlocal identities
        calls.append(request)
        assert request.method == "GET"
        assert request.headers["authorization"] == "Bearer synthetic-local-fixture"
        assert 'IdType="ImmutableId"' in request.headers["prefer"]
        if request.url.path == "/v1.0/me":
            identities += 1
            return httpx.Response(
                200, json={"id": "other" if switch and identities > 1 else "subject-fixture"}
            )
        if request.url.path == "/v1.0/me/mailFolders/inbox":
            return httpx.Response(200, json={"id": "folder-fixture"})
        return pages(request, len(calls))

    return handle, calls


def test_reads_delta_pages_preserves_opaque_link_and_redacts_result():
    cursor = DELTA + "?$skiptoken=a%2Bb%3D"
    final = DELTA + "?$deltatoken=private-cursor"

    def pages(request, _):
        if "$skiptoken" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "value": [{"id": "mail-1", "body": {"content": "PRIVATE_BODY"}}],
                    "@odata.nextLink": cursor,
                },
            )
        assert str(request.url) == cursor
        return httpx.Response(
            200,
            json={
                "value": [{"id": "mail-1"}, {"id": "mail-2", "@removed": {"reason": "deleted"}}],
                "@odata.deltaLink": final,
            },
        )

    handle, calls = fixture(pages)
    result = run(handle)
    assert result.delta_link == final
    assert result.next_link is None
    assert result.summary == {
        "state": "complete_round",
        "pages": 2,
        "records": 3,
        "unique_ids": 2,
        "body_records": 1,
        "removed_from_folder_records": 1,
    }
    assert len(calls) == 5
    assert "private-cursor" not in repr(result)
    assert "PRIVATE_BODY" not in repr(result)
    assert "subject-fixture" not in repr(result)


@pytest.mark.parametrize(
    "cursor",
    [
        "https://evil.example/v1.0/me/mailFolders/folder-fixture/messages/delta?$skiptoken=x",
        "http://graph.microsoft.com/v1.0/me/mailFolders/folder-fixture/messages/delta?$skiptoken=x",
        ROOT + "/users/other/messages/delta?$skiptoken=x",
        DELTA + "?access_token=secret",
        DELTA + "?$skiptoken=x#fragment",
        "https://user:password@graph.microsoft.com/v1.0/me/mailFolders/folder-fixture/messages/delta?$skiptoken=x",
    ],
)
def test_invalid_cursor_never_receives_bearer(cursor):
    handle, calls = fixture(lambda *_: pytest.fail("unsafe delta fetch"))
    with pytest.raises(ProbeBlocked, match="unsafe_cursor"):
        run(handle, cursor=cursor)
    assert all("/messages/delta" not in request.url.path for request in calls)


def test_partial_round_keeps_checkpoint_without_claiming_full_coverage():
    cursor = DELTA + "?$skiptoken=resume"
    handle, _ = fixture(
        lambda *_: httpx.Response(200, json={"value": [], "@odata.nextLink": cursor})
    )
    result = run(handle, max_pages=1)
    assert result.next_link == cursor
    assert result.delta_link is None
    assert result.summary["state"] == "partial_round"


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "reconnect_required"),
        (403, "consent_or_access_denied"),
        (410, "delta_reset_required"),
        (429, "rate_limited"),
        (503, "provider_unavailable"),
    ],
)
def test_controlled_errors_have_no_raw_provider_content_or_retry(status, code):
    handle, calls = fixture(
        lambda *_: httpx.Response(
            status, text="PRIVATE_PROVIDER_ERROR", headers={"Retry-After": "120"}
        )
    )
    with pytest.raises(ProbeBlocked, match=code) as caught:
        run(handle)
    assert "PRIVATE" not in str(caught.value)
    assert caught.value.retry_after == (120 if status == 429 else None)
    assert len(calls) == 3


def test_account_switch_discards_checkpoint():
    handle, _ = fixture(
        lambda *_: httpx.Response(
            200, json={"value": [], "@odata.deltaLink": DELTA + "?$deltatoken=x"}
        ),
        switch=True,
    )
    with pytest.raises(ProbeBlocked, match="identity_mismatch"):
        run(handle)


def test_wrong_initial_identity_stops_before_mail_reads():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"id": "other-subject"})

    with pytest.raises(ProbeBlocked, match="identity_mismatch"):
        run(handle)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"value": []},
        {"value": {}, "@odata.deltaLink": DELTA + "?$deltatoken=x"},
        {
            "value": [],
            "@odata.deltaLink": DELTA + "?$deltatoken=x",
            "@odata.nextLink": DELTA + "?$skiptoken=x",
        },
        {"value": [{"body": "missing id"}], "@odata.deltaLink": DELTA + "?$deltatoken=x"},
    ],
)
def test_malformed_pages_do_not_return_a_checkpoint(payload):
    handle, _ = fixture(lambda *_: httpx.Response(200, json=payload))
    with pytest.raises(ProbeBlocked, match="invalid_response"):
        run(handle)


def test_redirect_is_never_followed_even_if_injected_client_allows_it():
    handle, calls = fixture(
        lambda *_: httpx.Response(302, headers={"Location": "https://evil.example/steal"})
    )
    with pytest.raises(ProbeBlocked, match="redirect_blocked"):
        run(handle)
    assert len(calls) == 3


def test_body_limit_and_html_login_are_controlled():
    for response, code in [
        (
            httpx.Response(
                200, content=b"x" * (1024 * 1024 + 1), headers={"content-type": "application/json"}
            ),
            "size_limit",
        ),
        (httpx.Response(200, text="PRIVATE_LOGIN_HTML"), "invalid_response"),
    ]:
        handle, _ = fixture(lambda *_, response=response: response)
        with pytest.raises(ProbeBlocked, match=code):
            run(handle)


def test_cycle_stops_and_does_not_create_successful_delta_link():
    cursor = DELTA + "?$skiptoken=cycle"
    handle, _ = fixture(
        lambda *_: httpx.Response(200, json={"value": [], "@odata.nextLink": cursor})
    )
    with pytest.raises(ProbeBlocked, match="cursor_cycle"):
        run(handle)


def test_resume_uses_saved_cursor_without_adding_query_parameters():
    cursor = DELTA + "?$deltatoken=resume%2Bopaque"

    def pages(request, _):
        assert str(request.url) == cursor
        return httpx.Response(
            200, json={"value": [], "@odata.deltaLink": DELTA + "?$deltatoken=new"}
        )

    handle, _ = fixture(pages)
    assert run(handle, cursor=cursor).summary["pages"] == 1


@pytest.mark.parametrize("max_pages", [0, 11, True, 1.5])
def test_invalid_bounds_do_not_make_any_request(max_pages):
    with pytest.raises(ProbeBlocked, match="invalid_probe_configuration"):
        run(lambda _: pytest.fail("unexpected request"), max_pages=max_pages)


def test_provider_cannot_redirect_bearer_through_next_link():
    handle, calls = fixture(
        lambda *_: httpx.Response(
            200,
            json={
                "value": [],
                "@odata.nextLink": "https://evil.example/steal?$skiptoken=private",
            },
        )
    )
    with pytest.raises(ProbeBlocked, match="unsafe_cursor"):
        run(handle)
    assert len(calls) == 3


def test_timeout_is_redacted_and_not_retried():
    def pages(request, _):
        raise httpx.ReadTimeout("PRIVATE_NETWORK_DETAIL", request=request)

    handle, calls = fixture(pages)
    with pytest.raises(ProbeBlocked, match="network_failure") as caught:
        run(handle)
    assert "PRIVATE" not in str(caught.value)
    assert len(calls) == 3


@pytest.mark.parametrize("retry_after", ["9999", "Wed, 21 Oct 2026 07:28:00 GMT", "-1"])
def test_unknown_backoff_is_not_shortened_into_a_retry_schedule(retry_after):
    handle, _ = fixture(lambda *_: httpx.Response(429, headers={"Retry-After": retry_after}))
    with pytest.raises(ProbeBlocked) as caught:
        run(handle)
    assert caught.value.retry_after is None
