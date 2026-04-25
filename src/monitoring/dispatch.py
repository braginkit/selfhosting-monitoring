from __future__ import annotations

from collections.abc import Awaitable, Callable

from monitoring.models import AlertEvent

AlertSender = Callable[[AlertEvent], Awaitable[None]]


class AlertDispatcher:
    def __init__(self, channel_priority: list[str], strategies: dict[str, AlertSender]) -> None:
        self._channel_priority = channel_priority
        self._strategies = strategies

    async def dispatch(self, event: AlertEvent) -> str:
        errors: list[str] = []
        for channel in self._channel_priority:
            strategy = self._strategies.get(channel)
            if strategy is None:
                errors.append(f"Unknown channel '{channel}'")
                continue
            try:
                await strategy(event)
                return channel
            except Exception as exc:
                errors.append(f"{channel}: {exc}")

        raise RuntimeError("No alert strategy succeeded: " + " | ".join(errors))
