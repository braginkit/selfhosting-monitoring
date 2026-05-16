#!/usr/bin/env python3
"""Send one test alert through configured channels (SMTP, then Matrix outbox fallback)."""

from __future__ import annotations

import argparse
import asyncio
import sys

from monitoring.config import get_settings
from monitoring.dispatch import AlertDispatcher
from monitoring.models import AlertEvent
from monitoring.notifiers.smtp_notifier import SmtpNotifier
from monitoring.outbox.redis_outbox import RedisOutbox
from redis.asyncio import Redis


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix-only",
        action="store_true",
        help="Enqueue to Matrix outbox only (tests matrix-bot fallback path).",
    )
    args = parser.parse_args()
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    outbox = RedisOutbox(redis=redis, key_prefix=settings.redis_key_prefix)
    smtp = SmtpNotifier(settings)
    dispatcher = AlertDispatcher(
        channel_priority=settings.alert_channels,
        strategies={"smtp": smtp.send, "matrix_outbox": outbox.enqueue},
    )
    event = AlertEvent(
        target="smoke_test",
        severity="down",
        title="[TEST] SelfHosting monitoring alert",
        body="Manual smoke test from send-test-alert.py",
    )
    if args.matrix_only:
        await outbox.enqueue(event)
        print("OK: enqueued for matrix-bot")
        return 0

    channel = await dispatcher.dispatch(event)
    print(f"OK: dispatched via {channel}")
    if channel == "matrix_outbox":
        print("Check matrix-bot logs for delivery to the alerts room.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
