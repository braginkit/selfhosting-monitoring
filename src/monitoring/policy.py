from __future__ import annotations

from datetime import UTC, datetime, timedelta

from monitoring.models import AlertEvent, CheckResult
from monitoring.state.redis_state import RedisStateStore


class AlertPolicy:
    def __init__(
        self,
        store: RedisStateStore,
        failure_threshold_attempts: int,
        reminder_interval_seconds: int,
    ) -> None:
        self._store = store
        self._threshold = failure_threshold_attempts
        self._reminder_interval = timedelta(seconds=reminder_interval_seconds)

    async def evaluate(self, result: CheckResult) -> list[AlertEvent]:
        now = datetime.now(UTC)
        state = await self._store.get(result.target)
        events: list[AlertEvent] = []

        if result.ok:
            if state.status == "down":
                events.append(
                    AlertEvent(
                        target=result.target,
                        severity="recovery",
                        title=f"[RECOVERY] {result.target} is UP",
                        body=f"Service recovered at {now.isoformat()}.\nPrevious issue: {state.last_failure_reason}",
                    )
                )
            await self._store.reset(result.target)
            return events

        state.fail_count += 1
        state.status = "down"
        state.last_failure_reason = result.reason
        if state.first_failed_at is None:
            state.first_failed_at = now

        should_alert = False
        if state.fail_count == self._threshold:
            should_alert = True
        elif state.fail_count > self._threshold and state.last_alert_at:
            should_alert = (now - state.last_alert_at) >= self._reminder_interval

        if should_alert:
            state.last_alert_at = now
            events.append(
                AlertEvent(
                    target=result.target,
                    severity="down",
                    title=f"[ALERT] {result.target} is DOWN",
                    body=(
                        f"Status check failed {state.fail_count} times.\n"
                        f"Last error: {result.reason}\n"
                        f"First failure: {state.first_failed_at.isoformat() if state.first_failed_at else 'unknown'}\n"
                        f"Checked at: {result.checked_at.isoformat()}"
                    ),
                )
            )

        await self._store.save(state)
        return events
