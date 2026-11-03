"""Explicit operator entrypoint for persisted course checks; inactive until launched."""

import argparse
import json
import logging
import signal
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

from runtime.supervisor import run_course_supervision_once
from shared.budgeted_model import BudgetedMetaRouter
from shared.config import Settings
from shared.db import Store

log = logging.getLogger(__name__)


def tick(store, model, *, limit=20, queue_offers=False, stopped=lambda: False):
    """One bounded scheduling pass. Identities come only from the internal Store."""
    counts = {"checked": 0, "queued": 0, "errors": 0}
    for row in store.due_course_supervisions(limit=limit):
        if stopped():
            break
        try:
            result = run_course_supervision_once(store, model, row["user_id"], row["id"])
            if result is not None:
                counts["checked"] += 1
        except Exception:
            # Runtime holds failed/unknown inference. Never repeat the model call
            # here or log exception contents (which can contain private sources).
            counts["errors"] += 1
            log.warning("course_service_item_failed")
    if queue_offers and not stopped():
        # Recover a committed offer independently of paid model due times. These
        # are hints, not permits; enqueue rechecks current source/consent fences.
        for row in store.pending_course_offer_deliveries(limit=limit):
            if stopped():
                break
            try:
                store.enqueue_course_offer(row["user_id"], row["supervision_id"], row["offer_id"])
                counts["queued"] += 1
            except Exception:
                counts["errors"] += 1
                log.warning("course_service_enqueue_failed")
    return counts


def health(path, state, counts):
    if path is None:
        return
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(
            {"schema_version": 1, "state": state, "at": datetime.now(UTC).isoformat(), **counts}
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run explicitly activated budgeted course checks")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--limit", type=int, default=20, choices=range(1, 101))
    parser.add_argument("--poll-seconds", type=int, default=10, choices=range(1, 61))
    parser.add_argument("--queue-offers", action="store_true")
    parser.add_argument("--health-file", type=Path)
    parser.add_argument("--stop-file", type=Path)
    args = parser.parse_args(argv)
    settings = Settings()
    if not all(
        (
            settings.database_url,
            settings.meta_api_key,
            settings.meta_budget_key,
            settings.meta_input_usd_per_million,
            settings.meta_output_usd_per_million,
        )
    ):
        parser.error("Configure database, development model key, budget key and verified prices")
    logging.basicConfig(level=logging.INFO)
    store = Store(settings.database_url.get_secret_value(), canvas_origins=settings.canvas_origins)
    model = BudgetedMetaRouter(store, settings)
    stop = Event()

    def stopping():
        return stop.is_set() or (args.stop_file is not None and args.stop_file.exists())

    def stop_signal(*_):
        stop.set()

    previous = {sig: signal.signal(sig, stop_signal) for sig in (signal.SIGINT, signal.SIGTERM)}
    counts = {"checked": 0, "queued": 0, "errors": 0}
    try:
        health(args.health_file, "starting", counts)
        while not stopping():
            counts = tick(
                store, model, limit=args.limit, queue_offers=args.queue_offers, stopped=stopping
            )
            health(args.health_file, "degraded" if counts["errors"] else "running", counts)
            if args.once:
                break
            stop.wait(args.poll_seconds)
        health(args.health_file, "stopped", counts)
    except Exception:
        health(args.health_file, "failed", counts)
        log.error("course_service_failed")
        raise SystemExit(1) from None
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    main()
