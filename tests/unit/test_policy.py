from datetime import UTC, datetime, timedelta

import pytest

from monitoring.models import CheckResult
from monitoring.policy import AlertPolicy
from monitoring.state.redis_state import RedisStateStore


@pytest.mark.asyncio
async def test_alert_after_threshold(fake_redis):
    store = RedisStateStore(fake_redis, "test")
    policy = AlertPolicy(store=store, failure_threshold_attempts=5, reminder_interval_seconds=60)

    for attempt in range(1, 6):
        events = await policy.evaluate(
            CheckResult(
                target="appflowy",
                ok=False,
                reason=f"fail-{attempt}",
                checked_at=datetime.now(UTC),
            )
        )

    assert len(events) == 1
    assert events[0].severity == "down"


@pytest.mark.asyncio
async def test_recovery_resets_state(fake_redis):
    store = RedisStateStore(fake_redis, "test")
    policy = AlertPolicy(store=store, failure_threshold_attempts=1, reminder_interval_seconds=60)

    await policy.evaluate(
        CheckResult(
            target="appflowy",
            ok=False,
            reason="timeout",
            checked_at=datetime.now(UTC),
        )
    )
    recovery = await policy.evaluate(
        CheckResult(
            target="appflowy",
            ok=True,
            reason="ok",
            checked_at=datetime.now(UTC) + timedelta(minutes=1),
        )
    )
    assert len(recovery) == 1
    assert recovery[0].severity == "recovery"
    state = await store.get("appflowy")
    assert state.fail_count == 0


@pytest.mark.asyncio
async def test_reminder_after_interval(fake_redis):
    store = RedisStateStore(fake_redis, "test")
    policy = AlertPolicy(store=store, failure_threshold_attempts=1, reminder_interval_seconds=10)

    first = await policy.evaluate(CheckResult("appflowy", False, "down", datetime.now(UTC)))
    assert len(first) == 1

    no_reminder = await policy.evaluate(
        CheckResult("appflowy", False, "still down", datetime.now(UTC))
    )
    assert len(no_reminder) == 0

    state = await store.get("appflowy")
    state.last_alert_at = datetime.now(UTC) - timedelta(seconds=11)
    await store.save(state)

    reminder = await policy.evaluate(
        CheckResult("appflowy", False, "still down", datetime.now(UTC))
    )
    assert len(reminder) == 1


@pytest.mark.asyncio
async def test_no_alert_before_threshold(fake_redis) -> None:
    store = RedisStateStore(fake_redis, "test")
    policy = AlertPolicy(store=store, failure_threshold_attempts=5, reminder_interval_seconds=60)

    events = await policy.evaluate(CheckResult("matrix", False, "timeout", datetime.now(UTC)))

    assert events == []
    state = await store.get("matrix")
    assert state.fail_count == 1
    assert state.status == "down"


@pytest.mark.asyncio
async def test_ok_when_already_up_emits_no_recovery(fake_redis) -> None:
    store = RedisStateStore(fake_redis, "test")
    policy = AlertPolicy(store=store, failure_threshold_attempts=1, reminder_interval_seconds=60)

    events = await policy.evaluate(CheckResult("hoppscotch", True, "HTTP 200", datetime.now(UTC)))

    assert events == []


@pytest.mark.asyncio
async def test_down_alert_body_contains_failure_metadata(fake_redis) -> None:
    store = RedisStateStore(fake_redis, "test")
    policy = AlertPolicy(store=store, failure_threshold_attempts=1, reminder_interval_seconds=60)
    checked_at = datetime.now(UTC)

    events = await policy.evaluate(
        CheckResult("local_dns", False, "DNS error: timeout", checked_at)
    )

    assert len(events) == 1
    assert "[ALERT] local_dns is DOWN" in events[0].title
    assert "DNS error: timeout" in events[0].body
    assert checked_at.isoformat() in events[0].body
