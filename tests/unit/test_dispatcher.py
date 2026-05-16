import pytest

from monitoring.dispatch import AlertDispatcher
from monitoring.models import AlertEvent


@pytest.mark.asyncio
async def test_dispatcher_uses_first_successful_channel():
    calls: list[str] = []

    async def smtp_fail(event: AlertEvent) -> None:
        calls.append("smtp")
        raise RuntimeError("smtp down")

    async def matrix_queue_ok(event: AlertEvent) -> None:
        calls.append("matrix_outbox")

    dispatcher = AlertDispatcher(
        channel_priority=["smtp", "matrix_outbox"],
        strategies={
            "smtp": smtp_fail,
            "matrix_outbox": matrix_queue_ok,
        },
    )

    used = await dispatcher.dispatch(AlertEvent(target="svc", severity="down", title="t", body="b"))
    assert used == "matrix_outbox"
    assert calls == ["smtp", "matrix_outbox"]


@pytest.mark.asyncio
async def test_dispatcher_raises_when_all_channels_fail():
    async def fail_one(event: AlertEvent) -> None:
        raise RuntimeError("down1")

    async def fail_two(event: AlertEvent) -> None:
        raise RuntimeError("down2")

    dispatcher = AlertDispatcher(
        channel_priority=["smtp", "matrix_outbox"],
        strategies={
            "smtp": fail_one,
            "matrix_outbox": fail_two,
        },
    )

    with pytest.raises(RuntimeError):
        await dispatcher.dispatch(AlertEvent(target="svc", severity="down", title="t", body="b"))


@pytest.mark.asyncio
async def test_dispatcher_stops_after_first_success() -> None:
    calls: list[str] = []

    async def smtp_ok(event: AlertEvent) -> None:
        calls.append("smtp")

    async def matrix_ok(event: AlertEvent) -> None:
        calls.append("matrix_outbox")

    dispatcher = AlertDispatcher(
        channel_priority=["smtp", "matrix_outbox"],
        strategies={"smtp": smtp_ok, "matrix_outbox": matrix_ok},
    )

    used = await dispatcher.dispatch(AlertEvent(target="svc", severity="down", title="t", body="b"))

    assert used == "smtp"
    assert calls == ["smtp"]


@pytest.mark.asyncio
async def test_dispatcher_reports_unknown_channel() -> None:
    dispatcher = AlertDispatcher(
        channel_priority=["pagerduty"],
        strategies={},
    )

    with pytest.raises(RuntimeError, match="Unknown channel 'pagerduty'"):
        await dispatcher.dispatch(AlertEvent(target="svc", severity="down", title="t", body="b"))
