from datetime import UTC, datetime, timedelta

import pytest

from shared.freshness import canvas_freshness, legacy_freshness

NOW = datetime(2026, 10, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    "age,usable",
    [
        (timedelta(hours=24), True),
        (timedelta(hours=24, microseconds=1), False),
        (-timedelta(minutes=5), True),
        (-timedelta(minutes=5, microseconds=1), False),
    ],
)
def test_legacy_boundaries(age, usable):
    assert legacy_freshness(NOW - age, now=NOW).usable is usable


@pytest.mark.parametrize("value", [None, "2026-10-30", datetime(2026, 10, 30)])
def test_unknown_timestamps_fail_closed(value):
    assert legacy_freshness(value, now=NOW).reason == "unknown_time"


def canvas(**changes):
    args = dict(
        observed_at=NOW,
        received_at=NOW,
        connection_state="connected",
        current_generation=2,
        observation_generation=2,
        selected=True,
        item_coverage="complete",
        resource_coverage="complete",
        historical=False,
        missing_pending_confirmation=False,
        now=NOW,
    )
    return canvas_freshness(**(args | changes))


@pytest.mark.parametrize(
    "changes",
    [
        dict(connection_state="disconnected"),
        dict(connection_state="pending"),
        dict(observation_generation=1),
        dict(current_generation=True),
        dict(observation_generation=None),
        dict(selected=None),
        dict(selected=1),
        dict(item_coverage="partial"),
        dict(resource_coverage="restricted"),
        dict(resource_coverage=None),
        dict(historical=True),
        dict(historical=None),
        dict(missing_pending_confirmation=True),
        dict(missing_pending_confirmation=None),
        dict(observed_at=None),
        dict(received_at=datetime(2026, 10, 30)),
        dict(observed_at=NOW + timedelta(minutes=6)),
    ],
)
def test_canvas_untrusted_or_incomplete_inputs_fail_closed(changes):
    assert not canvas(**changes).usable


@pytest.mark.parametrize("purpose,hours", [("inspect", 24), ("draft", 6), ("act", 1)])
def test_canvas_purpose_boundaries_and_receipt_cannot_refresh_old_content(purpose, hours):
    old = NOW - timedelta(hours=hours)
    assert canvas(purpose=purpose, observed_at=old).usable
    assert not canvas(purpose=purpose, observed_at=old - timedelta(microseconds=1)).usable
    assert not canvas(purpose=purpose, received_at=old - timedelta(microseconds=1)).usable


def test_urgent_checks_expire_after_thirty_minutes():
    assert canvas(urgent=True, observed_at=NOW - timedelta(minutes=30)).usable
    assert not canvas(urgent=True, observed_at=NOW - timedelta(minutes=30, microseconds=1)).usable


@pytest.mark.parametrize(
    "changes",
    [dict(purpose="unknown"), dict(purpose=[]), dict(urgent=1), dict(now=datetime(2026, 10, 30))],
)
def test_invalid_policy_configuration_rejected(changes):
    with pytest.raises(ValueError):
        canvas(**changes)
