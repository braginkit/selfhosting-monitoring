from __future__ import annotations

from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Literal, cast

from redis.asyncio import Redis

from monitoring.models import IncidentState


def _fmt(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(UTC).isoformat()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class RedisStateStore:
    def __init__(self, redis: Redis, key_prefix: str) -> None:
        self._redis = redis
        self._prefix = key_prefix

    def _key(self, target: str) -> str:
        return f"{self._prefix}:incident:{target}"

    async def get(self, target: str) -> IncidentState:
        data = await cast(Awaitable[dict[str, str]], self._redis.hgetall(self._key(target)))
        if not data:
            return IncidentState(
                target=target,
                fail_count=0,
                status="up",
                first_failed_at=None,
                last_alert_at=None,
                last_failure_reason=None,
            )
        status_raw = data.get("status", "up")
        status: Literal["up", "down"] = "down" if status_raw == "down" else "up"
        return IncidentState(
            target=target,
            fail_count=int(data.get("fail_count", "0")),
            status=status,
            first_failed_at=_parse(data.get("first_failed_at")),
            last_alert_at=_parse(data.get("last_alert_at")),
            last_failure_reason=data.get("last_failure_reason"),
        )

    async def save(self, state: IncidentState) -> None:
        await cast(
            Awaitable[int],
            self._redis.hset(
                self._key(state.target),
                mapping={
                    "fail_count": str(state.fail_count),
                    "status": state.status,
                    "first_failed_at": _fmt(state.first_failed_at),
                    "last_alert_at": _fmt(state.last_alert_at),
                    "last_failure_reason": state.last_failure_reason or "",
                },
            ),
        )

    async def reset(self, target: str) -> None:
        await cast(Awaitable[int], self._redis.delete(self._key(target)))
