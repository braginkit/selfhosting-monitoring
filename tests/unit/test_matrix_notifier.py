from __future__ import annotations

from monitoring.models import AlertEvent
from monitoring.notifiers.matrix_notifier import MatrixNotifier


class _FakeMatrixClient:
    def __init__(self, homeserver: str, user_id: str) -> None:
        self.homeserver = homeserver
        self.user_id = user_id
        self.access_token: str | None = None
        self.room_send_called = False
        self.closed = False
        self.last_room_id: str | None = None
        self.last_body: str | None = None

    async def room_send(self, room_id: str, message_type: str, content: dict[str, str]) -> None:
        self.room_send_called = True
        self.last_room_id = room_id
        self.last_body = content["body"]

    async def close(self) -> None:
        self.closed = True


async def test_matrix_notifier_send_and_close(fake_settings, monkeypatch) -> None:
    monkeypatch.setattr("monitoring.notifiers.matrix_notifier.AsyncClient", _FakeMatrixClient)

    notifier = MatrixNotifier(fake_settings)
    event = AlertEvent(target="svc", severity="down", title="Service DOWN", body="details")

    await notifier.send(event)
    await notifier.close()

    client = notifier._client
    assert isinstance(client, _FakeMatrixClient)
    assert client.room_send_called is True
    assert client.last_room_id == fake_settings.matrix_room_id
    assert client.last_body == "Service DOWN\n\ndetails"
    assert client.closed is True
