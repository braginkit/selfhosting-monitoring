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
