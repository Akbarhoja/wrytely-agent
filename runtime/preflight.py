"""Secret-free installation checks. Never infer, migrate, enroll or send messages."""

import argparse
import hashlib
import json
from pathlib import Path

import psycopg
from pydantic import ValidationError
from pydantic_settings import SettingsError

from integrations.telegram import bot_id_for_token, verify_webhook
from shared.config import Settings

PROFILES = ("api", "supervisor", "telegram", "all")


def configuration_checks(settings, profile):
    """Presence/compatibility is not proof of credentials, grants or live access."""
    if profile not in PROFILES:
        raise ValueError("Unknown preflight profile")
    checks = []

    def present(value):
        if hasattr(value, "get_secret_value"):
            value = value.get_secret_value()
        return isinstance(value, str) and bool(value.strip())

    def check(name, passed, remedy):
        checks.append(
            {
                "name": name,
                "state": "configured" if passed else "missing_or_invalid",
                "help": remedy,
            }
        )

    check(
        "database",
        present(settings.database_url),
        "Set AGENT_DATABASE_URL to an isolated database.",
    )
    if profile in {"api", "all"}:
        check(
            "authentication",
            present(settings.clerk_issuer)
            and present(settings.clerk_jwt_key)
            and bool(settings.authorized_parties),
            "Set AGENT_CLERK_ISSUER, AGENT_CLERK_JWT_KEY and AGENT_AUTHORIZED_PARTIES "
            "for the same Clerk instance as the frontend.",
        )
        check(
            "canvas",
            bool(settings.canvas_origins and settings.canvas_document_extractors),
            "Set approved AGENT_CANVAS_ORIGINS and AGENT_CANVAS_DOCUMENT_EXTRACTORS; "
            "then package the extension for this API.",
        )
    if profile in {"supervisor", "all"}:
        check(
            "model_credential",
            present(
                settings.fireworks_api_key
                if settings.meta_provider == "fireworks"
                else settings.meta_api_key
            ),
            "Set AGENT_FIREWORKS_API_KEY for provider fireworks, or AGENT_META_API_KEY "
            "for provider meta. Keys are never inferred from the other provider.",
        )
        check(
            "model_options",
            settings.meta_provider != "fireworks"
            or settings.meta_reasoning_effort in {None, "low", "medium", "high"},
            "Fireworks supports unset/low/medium/high AGENT_META_REASONING_EFFORT.",
        )
        check(
            "model_budget_configuration",
            bool(
                settings.meta_budget_key
                and settings.meta_input_usd_per_million
                and settings.meta_output_usd_per_million
            ),
            "Set AGENT_META_BUDGET_KEY and verified nonzero input/output prices. "
            "An enabled cumulative database budget and student grant are also required.",
        )
    if profile in {"telegram", "all"}:
        valid_token = False
        if settings.telegram_bot_token:
            try:
                bot_id_for_token(settings.telegram_bot_token.get_secret_value())
                valid_token = True
            except ValueError:
                pass
        check(
            "telegram_bot",
            valid_token and bool(settings.telegram_bot_username),
            "Set AGENT_TELEGRAM_BOT_TOKEN and AGENT_TELEGRAM_BOT_USERNAME from your own bot.",
        )
        secret = (
            settings.telegram_webhook_secret.get_secret_value()
            if settings.telegram_webhook_secret
            else None
        )
        check(
            "telegram_webhook",
            verify_webhook(secret, secret),
            "Set AGENT_TELEGRAM_WEBHOOK_SECRET (32-256 URL-safe characters). "
            "Register the HTTPS webhook separately; this check does not contact Telegram.",
        )
    return checks


def expected_migrations():
    paths = sorted((Path(__file__).parents[1] / "contracts").glob("[0-9]*_*.sql"))
    return {
        path.name.split("_", 1)[0]: hashlib.sha256(path.read_text().encode()).hexdigest()
        for path in paths
    }


def database_check(database_url):
    """Explicit opt-in: read only the migration ledger, never student data."""
    if not database_url:
        return {"state": "not_checked", "reason": "database_not_configured"}
    try:
        with psycopg.connect(database_url, connect_timeout=5) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '5s'")
            rows = conn.execute("SELECT version, checksum FROM wrytely_agent.migrations").fetchall()
            applied = dict(rows)
            expected = expected_migrations()
            if set(applied) - set(expected):
                reason = "database_newer_than_checkout"
            elif any(applied[v] != digest for v, digest in expected.items() if v in applied):
                reason = "migration_checksum_mismatch"
            elif set(expected) - set(applied):
                reason = "migrations_pending"
            else:
                return {"state": "verified", "reason": "migration_ledger_matches"}
            return {"state": "blocked", "reason": reason}
    except psycopg.errors.UndefinedTable:
        return {"state": "blocked", "reason": "migrations_pending"}
    except Exception:
        # Driver exceptions can include DSNs, hosts and passwords. Never print them.
        return {"state": "blocked", "reason": "database_unreachable_or_access_denied"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="all")
    parser.add_argument(
        "--database-check",
        action="store_true",
        help="Read the configured database migration ledger",
    )
    args = parser.parse_args(argv)
    report = {
        "schema_version": 1,
        "profile": args.profile,
        "configuration_complete": False,
        "live_agent_verified": False,
        "checks": [],
        "database": {"state": "not_checked", "reason": "explicit_opt_in_required"},
    }
    try:
        settings = Settings()
    except (ValidationError, SettingsError):
        report["configuration_error"] = "invalid_environment_configuration"
    else:
        report["checks"] = configuration_checks(settings, args.profile)
        report["configuration_complete"] = all(
            check["state"] == "configured" for check in report["checks"]
        )
        if args.database_check:
            report["database"] = database_check(
                settings.database_url.get_secret_value() if settings.database_url else None
            )
    print(json.dumps(report, indent=2))
    return (
        0
        if report["configuration_complete"]
        and (not args.database_check or report["database"]["state"] == "verified")
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
