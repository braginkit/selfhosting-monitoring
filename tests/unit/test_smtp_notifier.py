from __future__ import annotations

from monitoring.models import AlertEvent
from monitoring.notifiers.smtp_notifier import SmtpNotifier


class _FakeSmtpClient:
    def __init__(self) -> None:
        self.connected = False
        self.logged_in = False
        self.sent_subject: str | None = None
        self.quit_called = False

    async def connect(self) -> None:
        self.connected = True

    async def login(self, username: str, password: str) -> None:
        self.logged_in = True

    async def send_message(self, message) -> None:  # noqa: ANN001
        self.sent_subject = str(message["Subject"])

    async def quit(self) -> None:
        self.quit_called = True


async def test_smtp_notifier_sends_message(fake_settings, monkeypatch) -> None:
    fake_client = _FakeSmtpClient()
    monkeypatch.setattr(
        "monitoring.notifiers.smtp_notifier.aiosmtplib.SMTP", lambda **kwargs: fake_client
    )

    notifier = SmtpNotifier(fake_settings)
    event = AlertEvent(target="svc", severity="down", title="Service DOWN", body="details")

    await notifier.send(event)

    assert fake_client.connected is True
    assert fake_client.logged_in is True
    assert fake_client.sent_subject == "Service DOWN"
    assert fake_client.quit_called is True
