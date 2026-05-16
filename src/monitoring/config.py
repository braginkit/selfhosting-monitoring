from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _monitor_alias(field_name: str) -> str:
    return f"MONITOR_{field_name.upper()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.base", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        alias_generator=_monitor_alias,
        populate_by_name=True,
    )

    env_name: str = "production"
    poll_interval_seconds: int = 60
    failure_retry_interval_seconds: int = 60
    failure_threshold_attempts: int = 5
    reminder_interval_seconds: int = 28800

    redis_url: str
    redis_key_prefix: str = "selfhost_monitor"

    smtp_host: str
    smtp_port: int = 587
    smtp_starttls: bool = True
    smtp_username: str
    smtp_password: str
    smtp_from: str
    smtp_to: str

    matrix_homeserver: str
    matrix_user_id: str
    matrix_access_token: str
    matrix_room_id: str

    alert_channel_priority: str = "smtp,matrix_outbox"
    targets_file: str = "targets.yml"

    smtp_delivery_tracking_enabled: bool = True
    smtp_delivery_grace_seconds: int = 120
    smtp_delivery_timeout_seconds: int = 600
    mail_log_dir: str = "/var/log/mail"

    @property
    def targets_path(self) -> Path:
        return Path(self.targets_file).resolve()

    @property
    def alert_channels(self) -> list[str]:
        return [item.strip() for item in self.alert_channel_priority.split(",") if item.strip()]

    @field_validator("alert_channel_priority")
    @classmethod
    def _validate_channel_priority(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("MONITOR_ALERT_CHANNEL_PRIORITY must not be empty")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
