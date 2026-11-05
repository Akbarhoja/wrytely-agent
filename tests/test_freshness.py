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


# Fixed instants and a real named zone reproduce DST issues independently of the
# machine's current date and timezone. Compare age in elapsed time, not wall time.
@pytest.mark.parametrize(
    "stamp", ["2025-11-02T07:30:00+00:00", "2025-11-02T08:30:00+00:00", "2025-03-09T08:30:00+00:00"]
)
@pytest.mark.parametrize("hours", [1, 6, 24])
def test_elapsed_ttl_is_invariant_to_dst_and_timestamp_representation(stamp, hours):
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/Denver")
    checked = datetime.fromisoformat(stamp)
    boundary = checked + timedelta(hours=hours)
    for observed in (checked, checked.astimezone(zone)):
        for clock in (boundary, boundary.astimezone(zone)):
            if hours == 24:
                result = legacy_freshness(observed, now=clock)
            else:
                result = canvas(
                    observed_at=observed,
                    received_at=observed,
                    now=clock,
                    purpose="act" if hours == 1 else "draft",
                )
            assert result.usable
            assert result.expires_at.astimezone(UTC) == boundary
        late = boundary + timedelta(microseconds=1)
        result = (
            legacy_freshness(observed, now=late)
            if hours == 24
            else canvas(
                observed_at=observed,
                received_at=observed,
                now=late,
                purpose="act" if hours == 1 else "draft",
            )
        )
        assert not result.usable


@pytest.mark.parametrize(
    "clock_stamp,observed_stamp",
    [
        ("2025-11-02T07:55:00+00:00", "2025-11-02T08:01:00+00:00"),
        ("2025-03-09T08:55:00+00:00", "2025-03-09T09:01:00+00:00"),
    ],
)
def test_future_limit_uses_elapsed_minutes_across_clock_changes(clock_stamp, observed_stamp):
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/Denver")
    now = datetime.fromisoformat(clock_stamp).astimezone(zone)
    observed = datetime.fromisoformat(observed_stamp).astimezone(zone)
    assert legacy_freshness(observed, now=now).reason == "future_observation"
    assert (
        canvas(observed_at=observed, received_at=observed, now=now).reason == "future_observation"
    )


def test_receipt_cannot_hide_older_evidence_when_wall_clock_order_reverses():
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/Denver")
    early = datetime.fromisoformat("2025-11-02T07:45:00+00:00").astimezone(zone)
    late = datetime.fromisoformat("2025-11-02T08:15:00+00:00").astimezone(zone)
    now = datetime.fromisoformat("2025-11-02T08:50:00+00:00")
    for observed, received in ((early, late), (late, early)):
        result = canvas(observed_at=observed, received_at=received, now=now, purpose="act")
        assert not result.usable and result.reason == "too_old"
        assert result.checked_at.astimezone(UTC) == early.astimezone(UTC)


def test_urgent_half_hour_expires_after_thirty_elapsed_minutes_across_fold():
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/Denver")
    observed = datetime.fromisoformat("2025-11-02T07:50:00+00:00").astimezone(zone)
    boundary = datetime.fromisoformat("2025-11-02T08:20:00+00:00")
    assert canvas(observed_at=observed, received_at=observed, now=boundary, urgent=True).usable
    assert not canvas(
        observed_at=observed,
        received_at=observed,
        now=boundary + timedelta(microseconds=1),
        urgent=True,
    ).usable
