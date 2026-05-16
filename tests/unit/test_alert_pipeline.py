"""End-to-end alert pipeline: policy thresholds + SMTP/Matrix dispatch."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from monitoring.dispatch import AlertDispatcher
from monitoring.models import AlertEvent, CheckResult
from monitoring.outbox.redis_outbox import RedisOutbox
from monitoring.policy import AlertPolicy
from monitoring.state.redis_state import RedisStateStore


@pytest.mark.asyncio
async def test_failure_threshold_then_smtp_success(fake_redis, fake_settings) -> None:
    store = RedisStateStore(fake_redis, fake_settings.redis_key_prefix)
    policy = AlertPolicy(
        store=store,
        failure_threshold_attempts=2,
        reminder_interval_seconds=3600,
    )
    sent: list[AlertEvent] = []

    async def smtp_ok(event: AlertEvent) -> None:
        sent.append(event)

    dispatcher = AlertDispatcher(
        channel_priority=["smtp", "matrix_outbox"],
        strategies={"smtp": smtp_ok, "matrix_outbox": _fail_enqueue},
    )

    for _ in range(2):
        events = await policy.evaluate(CheckResult("matrix", False, "err", datetime.now(UTC)))
        for event in events:
            await dispatcher.dispatch(event)

    assert len(sent) == 1
    assert sent[0].severity == "down"


@pytest.mark.asyncio
async def test_smtp_failure_falls_back_to_matrix_outbox(fake_redis, fake_settings) -> None:
    store = RedisStateStore(fake_redis, fake_settings.redis_key_prefix)
    outbox = RedisOutbox(fake_redis, fake_settings.redis_key_prefix)
    policy = AlertPolicy(store=store, failure_threshold_attempts=1, reminder_interval_seconds=3600)

    async def smtp_fail(_event: AlertEvent) -> None:
        raise ConnectionError("smtp unreachable")

    dispatcher = AlertDispatcher(
        channel_priority=["smtp", "matrix_outbox"],
        strategies={"smtp": smtp_fail, "matrix_outbox": outbox.enqueue},
    )

    events = await policy.evaluate(CheckResult("mail_smtp", False, "down", datetime.now(UTC)))
    channel = await dispatcher.dispatch(events[0])

    assert channel == "matrix_outbox"
    queued = await outbox.dequeue_blocking(timeout_seconds=1)
    assert queued is not None


@pytest.mark.asyncio
async def test_recovery_after_outage(fake_redis, fake_settings) -> None:
    store = RedisStateStore(fake_redis, fake_settings.redis_key_prefix)
    policy = AlertPolicy(store=store, failure_threshold_attempts=1, reminder_interval_seconds=3600)

    async def smtp_ok(_event: AlertEvent) -> None:
        return None

    dispatcher = AlertDispatcher(channel_priority=["smtp"], strategies={"smtp": smtp_ok})

    down_events = await policy.evaluate(CheckResult("appflowy", False, "503", datetime.now(UTC)))
    await dispatcher.dispatch(down_events[0])

    recovery_events = await policy.evaluate(
        CheckResult("appflowy", True, "HTTP 200", datetime.now(UTC))
    )
    channel = await dispatcher.dispatch(recovery_events[0])

    assert channel == "smtp"
    assert recovery_events[0].severity == "recovery"


async def _fail_enqueue(_event: AlertEvent) -> None:
    raise RuntimeError("should not run")
