from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from monitoring.delivery.mail_log import DeliveryStatus
from monitoring.delivery.store import SmtpDeliveryStore
from monitoring.delivery.tracker import SmtpDeliveryTracker, build_escalation_event
from monitoring.models import AlertEvent
from monitoring.outbox.redis_outbox import RedisOutbox


@pytest.mark.asyncio
async def test_tracker_escalates_bounced_delivery(fake_redis, fake_settings) -> None:
    store = SmtpDeliveryStore(fake_redis, fake_settings.redis_key_prefix)
    outbox = RedisOutbox(fake_redis, fake_settings.redis_key_prefix)
    log_dir = Path(__file__).resolve().parents[1] / "fixtures" / "mail_logs"

    tracker = SmtpDeliveryTracker(
        store=store,
        outbox=outbox,
        log_dir=log_dir,
        grace_seconds=0,
        timeout_seconds=60,
        enabled=True,
    )

    event = AlertEvent(target="mail_smtp", severity="down", title="[ALERT] down", body="orig")
    await store.register("<test-bounced@bragin.crazedns.ru>", event)

    old_sent_at = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    await fake_redis.hset(
        f"{fake_settings.redis_key_prefix}:smtp_delivery:test-bounced@bragin.crazedns.ru",
        mapping={"sent_at": old_sent_at},
    )

    await tracker.reconcile_and_escalate()

    updated = await store.get("<test-bounced@bragin.crazedns.ru>")
    assert updated is not None
    assert updated.status == DeliveryStatus.BOUNCED
    assert updated.matrix_escalated is True

    queued = await outbox.dequeue_blocking(timeout_seconds=1)
    assert queued is not None
    assert "[ESCALATION]" in queued.title
    assert "email channel" in queued.body.lower() or "smtp" in queued.body.lower()
    assert "mail error" in queued.body.lower()


@pytest.mark.asyncio
async def test_tracker_marks_delivered_without_matrix(fake_redis, fake_settings) -> None:
    store = SmtpDeliveryStore(fake_redis, fake_settings.redis_key_prefix)
    outbox = RedisOutbox(fake_redis, fake_settings.redis_key_prefix)
    log_dir = Path(__file__).resolve().parents[1] / "fixtures" / "mail_logs"

    tracker = SmtpDeliveryTracker(
        store=store,
        outbox=outbox,
        log_dir=log_dir,
        grace_seconds=0,
        timeout_seconds=60,
        enabled=True,
    )

    event = AlertEvent(target="matrix", severity="down", title="down", body="orig")
    await store.register("<test-delivered@bragin.crazedns.ru>", event)

    await tracker.reconcile_and_escalate()

    updated = await store.get("<test-delivered@bragin.crazedns.ru>")
    assert updated is not None
    assert updated.status == DeliveryStatus.DELIVERED
    assert updated.matrix_escalated is False
    assert await outbox.dequeue_blocking(timeout_seconds=1) is None


@pytest.mark.asyncio
async def test_tracker_skips_when_disabled(fake_redis, fake_settings) -> None:
    store = SmtpDeliveryStore(fake_redis, fake_settings.redis_key_prefix)
    outbox = RedisOutbox(fake_redis, fake_settings.redis_key_prefix)

    tracker = SmtpDeliveryTracker(
        store=store,
        outbox=outbox,
        log_dir=Path("/nonexistent"),
        grace_seconds=0,
        timeout_seconds=1,
        enabled=False,
    )

    await store.register("<x@bragin.crazedns.ru>", AlertEvent("x", "down", "t", "b"))
    await tracker.reconcile_and_escalate()

    assert await store.list_pending()


@pytest.mark.asyncio
async def test_tracker_timeout_escalates_unknown(fake_redis, fake_settings) -> None:
    store = SmtpDeliveryStore(fake_redis, fake_settings.redis_key_prefix)
    outbox = RedisOutbox(fake_redis, fake_settings.redis_key_prefix)

    tracker = SmtpDeliveryTracker(
        store=store,
        outbox=outbox,
        log_dir=Path("/nonexistent"),
        grace_seconds=0,
        timeout_seconds=1,
        enabled=True,
    )

    message_id = "<missing@bragin.crazedns.ru>"
    await store.register(message_id, AlertEvent("svc", "down", "down", "body"))
    old = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    await fake_redis.hset(
        f"{fake_settings.redis_key_prefix}:smtp_delivery:missing@bragin.crazedns.ru",
        mapping={"sent_at": old},
    )

    await tracker.reconcile_and_escalate()

    updated = await store.get(message_id)
    assert updated is not None
    assert updated.matrix_escalated is True
    queued = await outbox.dequeue_blocking(timeout_seconds=1)
    assert queued is not None
    assert "timeout" in queued.body.lower() or "unknown" in queued.body.lower()


def test_build_escalation_event_mentions_original_alert() -> None:
    from monitoring.delivery.store import SmtpDeliveryRecord

    record = SmtpDeliveryRecord(
        message_id="<x@bragin.crazedns.ru>",
        target="hoppscotch",
        severity="down",
        title="[ALERT] hoppscotch is DOWN",
        body="service failed",
        sent_at=datetime.now(UTC),
        status=DeliveryStatus.BOUNCED,
        last_error="status=bounced (Spamhaus PBL)",
        matrix_escalated=False,
    )

    event = build_escalation_event(record, status=DeliveryStatus.BOUNCED, error=record.last_error)

    assert "hoppscotch" in event.body
    assert "service failed" in event.body
    assert "Spamhaus" in event.body or "icloud" in event.body.lower()
