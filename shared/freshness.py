"""Server-owned evidence age policy. Freshness never grants identity, consent or readiness."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class Freshness:
    usable: bool
    reason: str
    checked_at: datetime | None = None
    expires_at: datetime | None = None


def _aware(value):
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _clock(now):
    now = datetime.now(UTC) if now is None else now
    if not _aware(now):
        raise ValueError("Aware policy clock required")
    return now


def _age(checked_at, now, ttl):
    if not _aware(checked_at):
        return Freshness(False, "unknown_time")
    if checked_at > now + timedelta(minutes=5):
        return Freshness(False, "future_observation")
    expires_at = checked_at + ttl
    return Freshness(
        now <= expires_at, "fresh" if now <= expires_at else "too_old", checked_at, expires_at
    )


def legacy_freshness(retrieved_at, *, now=None):
    """Existing snapshot/api/feed/group transport paths keep their 24h/5min bounds."""
    return _age(retrieved_at, _clock(now), timedelta(hours=24))


def canvas_freshness(
    *,
    observed_at,
    received_at,
    connection_state,
    current_generation,
    observation_generation,
    selected,
    item_coverage,
    resource_coverage,
    historical,
    missing_pending_confirmation,
    purpose="inspect",
    urgent=False,
    now=None,
):
    """Future reader foundation; caller derives all inputs from owned current DB state.

    Not connected to staged source activation, model tools or HTTP yet. Caller must
    validate ownership and exact version/observation/resource binding separately.
    """
    now = _clock(now)
    ttl_by_purpose = {
        "inspect": timedelta(hours=24),
        "draft": timedelta(hours=6),
        "act": timedelta(hours=1),
    }
    if not isinstance(purpose, str) or purpose not in ttl_by_purpose or type(urgent) is not bool:
        raise ValueError("Invalid freshness purpose/urgency")
    if connection_state != "connected":
        return Freshness(False, "connection_unavailable")
    if (
        type(current_generation) is not int
        or type(observation_generation) is not int
        or current_generation < 1
        or current_generation != observation_generation
    ):
        return Freshness(False, "generation_changed")
    if selected is not True:
        return Freshness(False, "not_selected")
    if historical is not False:
        return Freshness(False, "historical_or_unknown")
    if missing_pending_confirmation is not False:
        return Freshness(False, "missing_or_unknown")
    if item_coverage != "complete":
        return Freshness(False, "item_incomplete")
    if resource_coverage != "complete":
        return Freshness(False, "resource_incomplete")
    if not _aware(observed_at) or not _aware(received_at):
        return Freshness(False, "unknown_time")
    if max(observed_at, received_at) > now + timedelta(minutes=5):
        return Freshness(False, "future_observation")
    ttl = min(ttl_by_purpose[purpose], timedelta(minutes=30)) if urgent else ttl_by_purpose[purpose]
    return _age(min(observed_at, received_at), now, ttl)
