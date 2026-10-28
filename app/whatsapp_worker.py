"""Explicitly configured WhatsApp reply-delivery process; never runs migrations."""

import argparse
import logging
import time
from uuid import uuid4

import httpx

from integrations.whatsapp import WhatsAppAdapter
from integrations.whatsapp_delivery import run_once
from shared.config import Settings
from shared.db import Store

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Deliver authorized queued WhatsApp text replies")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    settings = Settings()
    if not all(
        (
            settings.database_url,
            settings.whatsapp_access_token,
            settings.whatsapp_api_version,
            settings.whatsapp_business_account_id,
            settings.whatsapp_phone_number_id,
        )
    ):
        parser.error(
            "Configure AGENT_DATABASE_URL, AGENT_WHATSAPP_ACCESS_TOKEN, "
            "AGENT_WHATSAPP_API_VERSION, AGENT_WHATSAPP_BUSINESS_ACCOUNT_ID "
            "and AGENT_WHATSAPP_PHONE_NUMBER_ID"
        )
    logging.basicConfig(level=logging.INFO)
    store = Store(settings.database_url.get_secret_value())
    worker_id = f"whatsapp-{uuid4()}"
    try:
        with httpx.Client(
            transport=httpx.HTTPTransport(retries=0),
            timeout=15,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            adapter = WhatsAppAdapter(
                client=client,
                token=settings.whatsapp_access_token.get_secret_value(),
                phone_number_id=settings.whatsapp_phone_number_id,
                api_version=settings.whatsapp_api_version,
            )
            while True:
                try:
                    outcome = run_once(
                        store,
                        adapter,
                        worker_id=worker_id,
                        business_id=settings.whatsapp_business_account_id,
                        phone_number_id=settings.whatsapp_phone_number_id,
                    )
                except Exception:
                    # Error text can contain credentials or message content. Do not
                    # log it, reuse a claim, or schedule a retry for that action.
                    log.error("whatsapp_delivery_iteration_failed")
                    if args.once:
                        raise SystemExit(1) from None
                    time.sleep(1)
                    continue
                if args.once:
                    return
                if outcome in ("idle", "held", "cancelled", "lease_lost"):
                    time.sleep(1)
    except KeyboardInterrupt:
        log.info("whatsapp_delivery_stopped")


if __name__ == "__main__":
    main()
