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
