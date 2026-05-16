from datetime import UTC, datetime

import pytest

from monitoring.dispatch import AlertDispatcher
from monitoring.models import AlertEvent
from monitoring.notifiers.smtp_notifier import SmtpNotifier
from monitoring.outbox.redis_outbox import RedisOutbox


@pytest.mark.asyncio
async def test_smtp_failure_goes_to_matrix_outbox(fake_settings, fake_redis, monkeypatch) -> None:
    outbox = RedisOutbox(fake_redis, fake_settings.redis_key_prefix)
    notifier = SmtpNotifier(fake_settings)

    async def _raise(*_args, **_kwargs) -> None:
        raise RuntimeError("smtp down")

    monkeypatch.setattr(notifier, "send", _raise)

    dispatcher = AlertDispatcher(
        channel_priority=fake_settings.alert_channels,
        strategies={"smtp": notifier.send, "matrix_outbox": outbox.enqueue},
    )

    event = AlertEvent(
        target="mail_smtp",
        severity="down",
        title="[ALERT] mail_smtp is DOWN",
        body=f"checked at {datetime.now(UTC).isoformat()}",
    )

    channel = await dispatcher.dispatch(event)

    assert channel == "matrix_outbox"
    queued = await outbox.dequeue_blocking(timeout_seconds=1)
    assert queued is not None
    assert queued.target == "mail_smtp"
