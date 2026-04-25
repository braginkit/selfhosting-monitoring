from __future__ import annotations

import json

from redis.asyncio import Redis

from monitoring.models import AlertEvent


class RedisOutbox:
    def __init__(self, redis: Redis, key_prefix: str) -> None:
        self._redis = redis
        self._key = f"{key_prefix}:matrix_outbox"

    async def enqueue(self, event: AlertEvent) -> None:
        payload = {"target": event.target, "severity": event.severity, "title": event.title, "body": event.body}
        await self._redis.lpush(self._key, json.dumps(payload))

    async def dequeue_blocking(self, timeout_seconds: int = 5) -> AlertEvent | None:
        item = await self._redis.brpop(self._key, timeout=timeout_seconds)
        if item is None:
            return None
        _, payload = item
        data = json.loads(payload)
        return AlertEvent(
            target=data["target"],
            severity=data["severity"],
            title=data["title"],
            body=data["body"],
        )
