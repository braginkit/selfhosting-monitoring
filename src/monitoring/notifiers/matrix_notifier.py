from __future__ import annotations

from nio import AsyncClient

from monitoring.config import Settings
from monitoring.models import AlertEvent


class MatrixNotifier:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncClient(settings.matrix_homeserver, settings.matrix_user_id)
        self._client.access_token = settings.matrix_access_token

    async def send(self, event: AlertEvent) -> None:
        message = f"{event.title}\n\n{event.body}"
        await self._client.room_send(
            room_id=self._settings.matrix_room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": message},
        )

    async def close(self) -> None:
        await self._client.close()
