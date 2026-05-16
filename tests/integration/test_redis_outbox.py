import pytest

from monitoring.models import AlertEvent
from monitoring.outbox.redis_outbox import RedisOutbox


@pytest.mark.asyncio
async def test_redis_outbox_roundtrip(fake_redis):
    outbox = RedisOutbox(fake_redis, "integration")
    event = AlertEvent(
        target="appflowy",
        severity="down",
        title="[ALERT] appflowy is DOWN",
        body="sample",
    )
    await outbox.enqueue(event)
    result = await outbox.dequeue_blocking(timeout_seconds=1)

    assert result is not None
    assert result.target == event.target
    assert result.title == event.title
    assert result.severity == event.severity
    assert result.body == event.body


@pytest.mark.asyncio
async def test_redis_outbox_fifo_order(fake_redis) -> None:
    outbox = RedisOutbox(fake_redis, "integration_fifo")
    first = AlertEvent(target="a", severity="down", title="first", body="1")
    second = AlertEvent(target="b", severity="down", title="second", body="2")

    await outbox.enqueue(first)
    await outbox.enqueue(second)

    dequeued_first = await outbox.dequeue_blocking(timeout_seconds=1)
    dequeued_second = await outbox.dequeue_blocking(timeout_seconds=1)

    assert dequeued_first is not None
    assert dequeued_second is not None
    assert dequeued_first.title == "first"
    assert dequeued_second.title == "second"


@pytest.mark.asyncio
async def test_redis_outbox_blocking_timeout_returns_none(fake_redis) -> None:
    outbox = RedisOutbox(fake_redis, "integration_empty")

    assert await outbox.dequeue_blocking(timeout_seconds=1) is None
