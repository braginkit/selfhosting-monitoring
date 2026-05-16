from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from redis.asyncio import Redis

from monitoring.delivery.mail_log import DeliveryStatus
from monitoring.models import AlertEvent, AlertSeverity


def _message_key(message_id: str) -> str:
    return message_id.strip().strip("<>").lower()


def _parse_severity(value: str) -> AlertSeverity:
    if value not in ("down", "recovery"):
        msg = f"invalid alert severity in store: {value!r}"
        raise ValueError(msg)
    return cast(AlertSeverity, value)


@dataclass(slots=True)
class SmtpDeliveryRecord:
    message_id: str
    target: str
    severity: AlertSeverity
    title: str
    body: str
    sent_at: datetime
    status: DeliveryStatus
    last_error: str | None
    matrix_escalated: bool


class SmtpDeliveryStore:
    def __init__(self, redis: Redis, key_prefix: str) -> None:
        self._redis = redis
        self._prefix = key_prefix

    def _hash_key(self, message_id: str) -> str:
        return f"{self._prefix}:smtp_delivery:{_message_key(message_id)}"

    def _pending_key(self) -> str:
        return f"{self._prefix}:smtp_delivery_pending"

    async def register(self, message_id: str, event: AlertEvent) -> None:
        now = datetime.now(UTC)
        mapping = {
            "message_id": message_id,
            "target": event.target,
            "severity": event.severity,
            "title": event.title,
            "body": event.body,
            "sent_at": now.isoformat(),
            "status": DeliveryStatus.PENDING.value,
            "last_error": "",
            "matrix_escalated": "0",
        }
        await cast(Awaitable[int], self._redis.hset(self._hash_key(message_id), mapping=mapping))
        await cast(
            Awaitable[int],
            self._redis.zadd(self._pending_key(), {message_id: now.timestamp()}),
        )

    async def list_pending(self) -> list[SmtpDeliveryRecord]:
        raw_ids = await cast(Awaitable[list[str]], self._redis.zrange(self._pending_key(), 0, -1))
        records: list[SmtpDeliveryRecord] = []
        for message_id in raw_ids:
            record = await self.get(message_id)
            if record is not None:
                records.append(record)
        return records

    async def get(self, message_id: str) -> SmtpDeliveryRecord | None:
        data = await cast(
            Awaitable[dict[str, str]], self._redis.hgetall(self._hash_key(message_id))
        )
        if not data:
            return None
        return SmtpDeliveryRecord(
            message_id=data["message_id"],
            target=data["target"],
            severity=_parse_severity(data["severity"]),
            title=data["title"],
            body=data["body"],
            sent_at=datetime.fromisoformat(data["sent_at"]),
            status=DeliveryStatus(data.get("status", DeliveryStatus.PENDING.value)),
            last_error=data.get("last_error") or None,
            matrix_escalated=data.get("matrix_escalated") == "1",
        )

    async def update_status(
        self,
        message_id: str,
        status: DeliveryStatus,
        *,
        last_error: str | None = None,
    ) -> None:
        mapping: dict[str, str] = {"status": status.value}
        if last_error is not None:
            mapping["last_error"] = last_error
        await cast(Awaitable[int], self._redis.hset(self._hash_key(message_id), mapping=mapping))
        if status in {DeliveryStatus.DELIVERED, DeliveryStatus.BOUNCED}:
            await cast(Awaitable[int], self._redis.zrem(self._pending_key(), message_id))

    async def mark_matrix_escalated(self, message_id: str) -> None:
        await cast(
            Awaitable[int],
            self._redis.hset(self._hash_key(message_id), mapping={"matrix_escalated": "1"}),
        )
