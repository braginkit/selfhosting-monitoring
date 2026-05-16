from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from monitoring.delivery.mail_log import (
    DeliveryStatus,
    ICLOUD_ISSUE_RE,
    inspect_mail_logs,
    read_mail_log_files,
)
from monitoring.delivery.store import SmtpDeliveryRecord, SmtpDeliveryStore
from monitoring.models import AlertEvent
from monitoring.outbox.redis_outbox import RedisOutbox

logger = logging.getLogger(__name__)


def build_escalation_event(
    record: SmtpDeliveryRecord, *, status: DeliveryStatus, error: str | None
) -> AlertEvent:
    icloud_hint = ""
    if error and ICLOUD_ISSUE_RE.search(error):
        icloud_hint = (
            "\nLikely cause: outbound path to iCloud (relay or recipient MX) rejected the message "
            "(for example Spamhaus PBL on WAN IP or iCloud sender policy)."
        )

    return AlertEvent(
        target=record.target,
        severity=record.severity,
        title=f"[ESCALATION] Email delivery failed: {record.title}",
        body=(
            "An alert was accepted by the local mailserver via SMTP, but delivery to the inbox "
            "did not complete.\n"
            f"Target: {record.target}\n"
            f"Delivery status: {status.value}\n"
            f"Message-ID: {record.message_id}\n"
            f"Original alert:\n{record.body}\n"
            f"Mail error: {error or 'no final status in logs within timeout'}"
            f"{icloud_hint}\n"
            "This Matrix message is sent because the email channel did not confirm delivery."
        ),
    )


class SmtpDeliveryTracker:
    def __init__(
        self,
        store: SmtpDeliveryStore,
        outbox: RedisOutbox,
        *,
        log_dir: Path,
        grace_seconds: int,
        timeout_seconds: int,
        enabled: bool = True,
    ) -> None:
        self._store = store
        self._outbox = outbox
        self._log_dir = log_dir
        self._grace = timedelta(seconds=grace_seconds)
        self._timeout = timedelta(seconds=timeout_seconds)
        self._enabled = enabled

    async def reconcile_and_escalate(self) -> None:
        if not self._enabled:
            return

        pending = await self._store.list_pending()
        if not pending:
            return

        log_text = read_mail_log_files(self._log_dir)
        now = datetime.now(UTC)

        for record in pending:
            age = now - record.sent_at
            if age < self._grace:
                continue

            status, error = inspect_mail_logs(log_text, record.message_id)

            if status == DeliveryStatus.PENDING and age >= self._timeout:
                status = DeliveryStatus.UNKNOWN
                error = error or "delivery not confirmed before timeout"

            if status == DeliveryStatus.DELIVERED:
                await self._store.update_status(record.message_id, DeliveryStatus.DELIVERED)
                logger.info("SMTP delivery confirmed for %s", record.message_id)
                continue

            if status in {DeliveryStatus.PENDING, DeliveryStatus.DEFERRED} and age < self._timeout:
                if status != record.status:
                    await self._store.update_status(record.message_id, status, last_error=error)
                continue

            if record.matrix_escalated:
                await self._store.update_status(record.message_id, status, last_error=error)
                continue

            final_status = status if status != DeliveryStatus.PENDING else DeliveryStatus.UNKNOWN
            await self._store.update_status(record.message_id, final_status, last_error=error)
            await self._outbox.enqueue(
                build_escalation_event(record, status=final_status, error=error)
            )
            await self._store.mark_matrix_escalated(record.message_id)
            logger.warning(
                "SMTP delivery %s for %s; escalated to Matrix (%s)",
                final_status.value,
                record.message_id,
                record.target,
            )
