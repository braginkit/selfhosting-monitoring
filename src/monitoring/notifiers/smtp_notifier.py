from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from monitoring.config import Settings
from monitoring.models import AlertEvent


class SmtpNotifier:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, event: AlertEvent) -> None:
        message = EmailMessage()
        message["From"] = self._settings.smtp_from
        message["To"] = self._settings.smtp_to
        message["Subject"] = event.title
        message.set_content(event.body)

        smtp = aiosmtplib.SMTP(
            hostname=self._settings.smtp_host,
            port=self._settings.smtp_port,
            timeout=10,
            start_tls=self._settings.smtp_starttls,
        )
        await smtp.connect()
        await smtp.login(self._settings.smtp_username, self._settings.smtp_password)
        await smtp.send_message(message)
        await smtp.quit()
