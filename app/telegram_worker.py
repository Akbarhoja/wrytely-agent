"""Explicit one-use Telegram dispatch process; no models or startup migrations."""

import argparse
import time
from pathlib import Path

import httpx

from contracts.models import DeliveryResult
from integrations.telegram import TelegramAdapter, bot_id_for_token
from shared.canvas_reads import SourceRefreshRequired
from shared.config import Settings
from shared.db import Store


def run_once(store, adapter, bot_id):
    if adapter.bot_id != bot_id:
        raise ValueError("Telegram bot mismatch")
    for hint in store.pending_telegram_preparations(bot_id):
        try:
            store.queue_telegram_preparation(
                hint["user_id"], bot_id, hint["supervision_id"], hint["preparation_id"]
            )
        except (ValueError, LookupError, SourceRefreshRequired):
            continue
    store.queue_telegram_replies(bot_id)
    claim = store.claim_telegram_delivery(bot_id)
    if claim is None:
        return "idle"
    if claim.bot_id != bot_id:
        raise ValueError("Telegram claim mismatch")
    permit = store.authorize_telegram_dispatch(claim)
    if permit.state != "permitted":
        return permit.state
    try:
        receipt = adapter.send(
            recipient=str(claim.chat_id), text=permit.content, action_id=claim.action_id
        )
    except Exception:
        receipt = DeliveryResult(state="unknown", internal_id=claim.action_id)
    store.finish_telegram_delivery(claim, receipt)
    return receipt.state


def main(argv=None):
    parser = argparse.ArgumentParser(description="Dispatch already-authorized Telegram intents")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=1)
    parser.add_argument("--stop-file", type=Path)
    args = parser.parse_args(argv)
    if not 1 <= args.max_iterations <= 1000:
        parser.error("Use 1 to 1000 bounded iterations")
    settings = Settings()
    try:
        bot = bot_id_for_token(settings.telegram_bot_token.get_secret_value())
        url = settings.database_url.get_secret_value()
    except (AttributeError, ValueError):
        parser.error("Configure database and Telegram credential")
    store = Store(url, canvas_origins=settings.canvas_origins)
    try:
        with httpx.Client(
            transport=httpx.HTTPTransport(retries=0),
            timeout=20,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            adapter = TelegramAdapter(settings.telegram_bot_token.get_secret_value(), client)
            for _ in range(1 if args.once else args.max_iterations):
                if args.stop_file and args.stop_file.exists():
                    return
                try:
                    run_once(store, adapter, bot)
                except Exception:
                    raise SystemExit("Telegram dispatch stopped; reconcile before retry") from None
                if args.once:
                    return
                time.sleep(1)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
