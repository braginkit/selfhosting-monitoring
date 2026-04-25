from __future__ import annotations

from collections.abc import Awaitable
import json
from typing import Literal, TypedDict, cast

from redis.asyncio import Redis

from monitoring.models import AlertEvent


class AlertPayload(TypedDict):
    target: str
    severity: Literal["down", "recovery"]
    title: str
    body: str


class RedisOutbox:
    def __init__(self, redis: Redis, key_prefix: str) -> None:
        self._redis = redis
        self._key = f"{key_prefix}:matrix_outbox"

    async def enqueue(self, event: AlertEvent) -> None:
        payload: AlertPayload = {
            "target": event.target,
            "severity": event.severity,
            "title": event.title,
            "body": event.body,
        }
        await cast(Awaitable[int], self._redis.lpush(self._key, json.dumps(payload)))

    async def dequeue_blocking(self, timeout_seconds: int = 5) -> AlertEvent | None:
        item = await cast(
            Awaitable[tuple[str, str] | None],
            self._redis.brpop(self._key, timeout=timeout_seconds),
        )
        if item is None:
            return None
        _, payload = item
        data = cast(AlertPayload, json.loads(payload))
        return AlertEvent(
            target=data["target"],
            severity=data["severity"],
            title=data["title"],
            body=data["body"],
        )
