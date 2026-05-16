from __future__ import annotations

import asyncio
import logging

from redis.asyncio import Redis

from monitoring.config import get_settings
from monitoring.notifiers.matrix_notifier import MatrixNotifier
from monitoring.outbox.redis_outbox import RedisOutbox


async def run_bot() -> None:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    outbox = RedisOutbox(redis=redis, key_prefix=settings.redis_key_prefix)
    notifier = MatrixNotifier(settings)

    try:
        while True:
            event = await outbox.dequeue_blocking(timeout_seconds=5)
            if event is None:
                await asyncio.sleep(1)
                continue
            await notifier.send(event)
            logging.warning("Alert sent via Matrix for %s (%s)", event.target, event.severity)
    finally:
        await notifier.close()


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
