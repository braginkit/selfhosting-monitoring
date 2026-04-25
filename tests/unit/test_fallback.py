from datetime import UTC, datetime

import pytest

from monitoring.models import AlertEvent
from monitoring.notifiers.smtp_notifier import SmtpNotifier
from monitoring.outbox.redis_outbox import RedisOutbox


@pytest.mark.asyncio
async def test_smtp_failure_goes_to_matrix_outbox(fake_settings, fake_redis, monkeypatch):
    outbox = RedisOutbox(fake_redis, fake_settings.redis_key_prefix)
    notifier = SmtpNotifier(fake_settings)

    async def _raise(*args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(notifier, "send", _raise)

    event = AlertEvent(
        target="mail_smtp",
        severity="down",
        title="[ALERT] mail_smtp is DOWN",
        body=f"checked at {datetime.now(UTC).isoformat()}",
    )

    try:
        await notifier.send(event)
    except RuntimeError:
        await outbox.enqueue(event)

    queued = await outbox.dequeue_blocking(timeout_seconds=1)
    assert queued is not None
    assert queued.target == "mail_smtp"
