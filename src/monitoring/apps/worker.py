from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis

from monitoring.checks import run_check
from monitoring.config import get_settings
from monitoring.dispatch import AlertDispatcher
from monitoring.notifiers.smtp_notifier import SmtpNotifier
from monitoring.outbox.redis_outbox import RedisOutbox
from monitoring.policy import AlertPolicy
from monitoring.state.redis_state import RedisStateStore
from monitoring.targets import load_targets


async def run_worker() -> None:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    store = RedisStateStore(redis=redis, key_prefix=settings.redis_key_prefix)
    outbox = RedisOutbox(redis=redis, key_prefix=settings.redis_key_prefix)
    policy = AlertPolicy(
        store=store,
        failure_threshold_attempts=settings.failure_threshold_attempts,
        reminder_interval_seconds=settings.reminder_interval_seconds,
    )
    smtp = SmtpNotifier(settings)
    dispatcher = AlertDispatcher(
        channel_priority=settings.alert_channels,
        strategies={
            "smtp": smtp.send,
            "matrix_outbox": outbox.enqueue,
        },
    )
    targets = load_targets(settings.targets_path)

    logging.info("Loaded %s targets", len(targets))
    logging.info("Alert channel priority: %s", " -> ".join(settings.alert_channels))
    while True:
        for target in targets:
            result = await run_check(target)
            events = await policy.evaluate(result)
            for event in events:
                try:
                    used_channel = await dispatcher.dispatch(event)
                    logging.warning(
                        "Alert sent via %s for %s (%s)",
                        used_channel,
                        event.target,
                        event.severity,
                    )
                except Exception as exc:
                    logging.exception("All alert channels failed for %s: %s", event.target, exc)
        await asyncio.sleep(settings.poll_interval_seconds)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
