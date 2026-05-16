from __future__ import annotations

import pytest

from monitoring.models import AlertEvent
from monitoring.notifiers.smtp_notifier import SmtpNotifier


class _FakeSmtpClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.connected = False
        self.logged_in: tuple[str, str] | None = None
        self.sent_message = None
        self.quit_called = False

    async def connect(self) -> None:
        self.connected = True

    async def login(self, username: str, password: str) -> None:
        self.logged_in = (username, password)

    async def send_message(self, message) -> None:  # noqa: ANN001
        self.sent_message = message

    async def quit(self) -> None:
        self.quit_called = True


async def test_smtp_notifier_sends_message(fake_settings, monkeypatch) -> None:
    fake_client = _FakeSmtpClient()
    captured: dict = {}

    def _factory(**kwargs):
        captured.update(kwargs)
        return fake_client

    monkeypatch.setattr("monitoring.notifiers.smtp_notifier.aiosmtplib.SMTP", _factory)

    notifier = SmtpNotifier(fake_settings)
    event = AlertEvent(target="svc", severity="down", title="Service DOWN", body="details")

    message_id = await notifier.send(event)

    assert message_id.endswith("@bragin.crazedns.ru>")
    assert captured["hostname"] == fake_settings.smtp_host
    assert captured["port"] == fake_settings.smtp_port
    assert captured["start_tls"] is fake_settings.smtp_starttls
    assert fake_client.connected is True
    assert fake_client.logged_in == (fake_settings.smtp_username, fake_settings.smtp_password)
    assert str(fake_client.sent_message["Subject"]) == "Service DOWN"
    assert str(fake_client.sent_message["From"]) == fake_settings.smtp_from
    assert str(fake_client.sent_message["To"]) == fake_settings.smtp_to
    assert fake_client.sent_message["Date"]
    assert str(fake_client.sent_message["Message-ID"]).endswith("@bragin.crazedns.ru>")
    assert fake_client.sent_message.get_payload().strip() == "details"
    assert fake_client.quit_called is True


async def test_smtp_notifier_propagates_connect_error(fake_settings, monkeypatch) -> None:
    class _FailingClient(_FakeSmtpClient):
        async def connect(self) -> None:
            raise ConnectionError("mail unreachable")

    monkeypatch.setattr(
        "monitoring.notifiers.smtp_notifier.aiosmtplib.SMTP",
        lambda **kwargs: _FailingClient(**kwargs),
    )

    notifier = SmtpNotifier(fake_settings)
    event = AlertEvent(target="mail_smtp", severity="down", title="down", body="body")

    with pytest.raises(ConnectionError, match="mail unreachable"):
        await notifier.send(event)


async def test_smtp_notifier_propagates_login_error(fake_settings, monkeypatch) -> None:
    class _AuthFailClient(_FakeSmtpClient):
        async def login(self, username: str, password: str) -> None:
            raise RuntimeError("535 auth failed")

    monkeypatch.setattr(
        "monitoring.notifiers.smtp_notifier.aiosmtplib.SMTP",
        lambda **kwargs: _AuthFailClient(**kwargs),
    )

    notifier = SmtpNotifier(fake_settings)
    event = AlertEvent(target="svc", severity="recovery", title="recovered", body="ok")

    with pytest.raises(RuntimeError, match="535 auth failed"):
        await notifier.send(event)
