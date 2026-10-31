"""Operator-only, expiring PKCE probe. No application routes or durable token cache.

Run as a module from the repository root using the isolated probe environment.
An authorization URL file contains only temporary OAuth request state, never tokens.
"""

import argparse
import json
import logging
import os
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

REDIRECT = "http://localhost:8765/"
SCOPES = ["User.Read", "Mail.Read"]
TTL = 300


class Blocked(Exception):
    """Only a fixed classification may leave the probe."""


class CallbackGate:
    def __init__(self, state, *, now=time.monotonic):
        self.state = state
        self.now = now
        self.deadline = now() + TTL
        self.response = None

    def accept(self, target, host):
        if self.response is not None or self.now() >= self.deadline:
            return False
        if host not in {"localhost:8765", "127.0.0.1:8765"} or len(target) > 16384:
            return False
        url = urlsplit(target)
        if url.scheme or url.netloc or url.path != "/" or url.fragment:
            return False
        try:
            pairs = parse_qsl(url.query, strict_parsing=True, max_num_fields=12)
        except ValueError:
            return False
        data = dict(pairs)
        if len(data) != len(pairs):
            return False
        state = data.get("state", "")
        if not secrets.compare_digest(state, self.state):
            return False
        if bool(data.get("code")) == bool(data.get("error")):
            return False
        # Descriptions/session identifiers are unnecessary and must never be logged.
        self.response = {k: data[k] for k in ("state", "code", "error") if k in data}
        return True

    def clear(self):
        self.response = None
        self.state = ""
        self.deadline = 0


def handler_for(gate):
    class Handler(BaseHTTPRequestHandler):
        callback_gate = gate

        def log_message(self, *_args):
            pass

        def do_GET(self):
            try:
                accepted = gate.accept(self.path, self.headers.get("Host", ""))
            except (ValueError, UnicodeError, TypeError):
                accepted = False
            self.send_response(200 if accepted else 400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.end_headers()
            self.wfile.write(
                b"Sign-in response received. Return to Codex." if accepted else b"Rejected."
            )

    return Handler


class LoopbackServer(HTTPServer):
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(3)
        return connection, address


def validated_identity(result, expected_tenant):
    claims = result.get("id_token_claims")
    if not isinstance(claims, dict) or not result.get("access_token"):
        raise Blocked("authorization_failed")
    try:
        tenant = str(UUID(claims["tid"]))
        subject = str(UUID(claims["oid"]))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise Blocked("identity_unavailable") from None
    if tenant != expected_tenant:
        raise Blocked("wrong_organization")
    granted = set(result.get("scope", "").split())
    if not set(SCOPES) <= granted or "refresh_token" in result:
        raise Blocked("unexpected_grant")
    return subject


def run(args, *, app_factory=None):
    # MSAL is isolated from normal project dependencies and imported only for execution.
    if app_factory is None:
        from msal import PublicClientApplication

        app_factory = PublicClientApplication
    logging.disable(logging.CRITICAL)
    gate = CallbackGate(secrets.token_urlsafe(32))
    app = flow = result = None
    url_file = Path(args.url_file)
    owns_url_file = False
    # Exclusive bind before any authorization request. Never listen on all interfaces.
    server = LoopbackServer(("127.0.0.1", 8765), handler_for(gate), bind_and_activate=False)
    server.allow_reuse_address = False
    try:
        server.server_bind()
        server.server_activate()
        server.timeout = 1
        app = app_factory(
            args.client_id,
            authority="https://login.microsoftonline.com/organizations",
            exclude_scopes=["offline_access"],
            enable_pii_log=False,
            timeout=15,
            # Default MSAL cache is in-memory; no broker/persistence adapter is installed.
        )
        flow = app.initiate_auth_code_flow(
            SCOPES,
            redirect_uri=REDIRECT,
            state=gate.state,
            prompt="select_account",
            response_mode="query",
        )
        auth_url = flow.get("auth_uri", "")
        parsed = urlsplit(auth_url)
        query = dict(parse_qsl(parsed.query))
        if (
            parsed.scheme != "https"
            or parsed.netloc != "login.microsoftonline.com"
            or query.get("code_challenge_method") != "S256"
            or not query.get("code_challenge")
            or query.get("state") != gate.state
            or query.get("redirect_uri") != REDIRECT
            or not set(SCOPES) <= set(query.get("scope", "").split())
            or not set(query.get("scope", "").split()) <= set(SCOPES) | {"openid", "profile"}
        ):
            raise Blocked("invalid_authorization_request")
        # O_EXCL avoids overwriting another run or following a pre-existing symlink.
        descriptor = os.open(url_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        owns_url_file = True
        with os.fdopen(descriptor, "w") as output:
            json.dump({"authorization_url": auth_url, "expires_in_seconds": TTL}, output)
        print("authorization_url_ready", flush=True)
        while gate.response is None and time.monotonic() < gate.deadline:
            server.handle_request()
        if gate.response is None:
            raise Blocked("sign_in_timed_out")
        if "error" in gate.response:
            raise Blocked("consent_or_sign_in_denied")
        result = app.acquire_token_by_auth_code_flow(flow, gate.response)
        subject = validated_identity(result, args.expected_tenant)
        if not args.read_inbox:
            return {"state": "sign_in_passed", "mail_read_attempted": False}
        import httpx
        from pydantic import SecretStr

        from integrations.outlook.read_probe import probe_inbox

        with httpx.Client(transport=httpx.HTTPTransport(retries=0), trust_env=False) as client:
            return probe_inbox(
                client,
                SecretStr(result["access_token"]),
                expected_subject=subject,
                max_pages=1,
            ).summary
    finally:
        server.server_close()
        if app is not None:
            for account in app.get_accounts():
                app.remove_account(account)
        if isinstance(flow, dict):
            flow.clear()
        if isinstance(result, dict):
            result.clear()
        gate.clear()
        if owns_url_file:
            url_file.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", required=True, type=lambda x: str(UUID(x)))
    parser.add_argument("--expected-tenant", required=True, type=lambda x: str(UUID(x)))
    parser.add_argument("--url-file", required=True)
    parser.add_argument(
        "--read-inbox", action="store_true", help="Requires separate live-read approval"
    )
    args = parser.parse_args()
    try:
        outcome = run(args)
    except Blocked as error:
        outcome = {"state": "blocked", "reason": str(error)}
    except Exception:
        # Never serialize exception/request/response objects that may retain tokens.
        outcome = {"state": "blocked", "reason": "operator_or_provider_failure"}
    print(json.dumps(outcome), flush=True)


if __name__ == "__main__":
    main()
