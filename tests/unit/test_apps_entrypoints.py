import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from monitoring.apps import matrix_bot, worker
from monitoring.models import AlertEvent, CheckResult, Target


@dataclass
class _Settings:
    redis_url: str = "redis://localhost:6379/0"
    redis_key_prefix: str = "test"
    failure_threshold_attempts: int = 5
    reminder_interval_seconds: int = 60
    alert_channels: list[str] = field(default_factory=lambda: ["smtp", "matrix_outbox"])
    targets_path: Path = Path("targets.yml")
    poll_interval_seconds: int = 1


class _FakeRedisFactory:
    @staticmethod
    def from_url(url: str, decode_responses: bool) -> object:
        return object()


@pytest.mark.asyncio
async def test_worker_run_single_iteration(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _Settings()

    class _FakePolicy:
        async def evaluate(self, result: CheckResult) -> list[AlertEvent]:
            return [AlertEvent(target=result.target, severity="down", title="down", body="body")]

    class _FakeDispatcher:
        async def dispatch(self, event: AlertEvent) -> str:
            return "smtp"

    class _FakeSmtpNotifier:
        async def send(self, event: AlertEvent) -> None:
            return None

    class _FakeOutbox:
        async def enqueue(self, event: AlertEvent) -> None:
            return None

    async def _fake_run_check(target: Target) -> CheckResult:
        return CheckResult(target=target.name, ok=False, reason="down", checked_at=datetime.now(UTC))

    async def _stop_sleep(seconds: int) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "Redis", _FakeRedisFactory)
    monkeypatch.setattr(worker, "RedisStateStore", lambda redis, key_prefix: object())
    monkeypatch.setattr(worker, "RedisOutbox", lambda redis, key_prefix: _FakeOutbox())
    monkeypatch.setattr(worker, "AlertPolicy", lambda **kwargs: _FakePolicy())
    monkeypatch.setattr(worker, "SmtpNotifier", lambda _settings: _FakeSmtpNotifier())
    monkeypatch.setattr(worker, "AlertDispatcher", lambda **kwargs: _FakeDispatcher())
    monkeypatch.setattr(
        worker,
        "load_targets",
        lambda _path: [Target(name="svc", type="http", url="https://example.invalid")],
    )
    monkeypatch.setattr(worker, "run_check", _fake_run_check)
    monkeypatch.setattr(worker.asyncio, "sleep", _stop_sleep)

    with pytest.raises(asyncio.CancelledError):
        await worker.run_worker()


@pytest.mark.asyncio
async def test_matrix_bot_sends_event_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _Settings()
    sent: list[AlertEvent] = []
    closed = {"value": False}

    class _FakeOutbox:
        def __init__(self) -> None:
            self._calls = 0

        async def dequeue_blocking(self, timeout_seconds: int = 5) -> AlertEvent | None:
            self._calls += 1
            if self._calls == 1:
                return AlertEvent(target="svc", severity="down", title="down", body="body")
            return None

    class _FakeNotifier:
        async def send(self, event: AlertEvent) -> None:
            sent.append(event)

        async def close(self) -> None:
            closed["value"] = True

    async def _stop_sleep(seconds: int) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(matrix_bot, "get_settings", lambda: settings)
    monkeypatch.setattr(matrix_bot, "Redis", _FakeRedisFactory)
    monkeypatch.setattr(matrix_bot, "RedisOutbox", lambda redis, key_prefix: _FakeOutbox())
    monkeypatch.setattr(matrix_bot, "MatrixNotifier", lambda _settings: _FakeNotifier())
    monkeypatch.setattr(matrix_bot.asyncio, "sleep", _stop_sleep)

    with pytest.raises(asyncio.CancelledError):
        await matrix_bot.run_bot()

    assert len(sent) == 1
    assert sent[0].target == "svc"
    assert closed["value"] is True


def test_main_wrappers(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"worker": False, "bot": False}

    async def _fake_worker() -> None:
        called["worker"] = True

    async def _fake_bot() -> None:
        called["bot"] = True

    monkeypatch.setattr(worker, "run_worker", _fake_worker)
    monkeypatch.setattr(matrix_bot, "run_bot", _fake_bot)

    worker.main()
    matrix_bot.main()

    assert called["worker"] is True
    assert called["bot"] is True
