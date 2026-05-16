from pathlib import Path

import pytest
from pydantic import ValidationError

from monitoring.config import Settings


def test_settings_loads_test_profile(fake_settings: Settings) -> None:
    assert fake_settings.env_name == "test"
    assert fake_settings.smtp_delivery_tracking_enabled is False
    assert fake_settings.mail_log_dir == "tests/fixtures/mail_logs"


def test_alert_channels_splits_and_strips(fake_settings: Settings) -> None:
    settings = fake_settings.model_copy(update={"alert_channel_priority": " smtp , matrix_outbox "})
    assert settings.alert_channels == ["smtp", "matrix_outbox"]


def test_alert_channel_priority_must_not_be_empty() -> None:
    root = Path(__file__).resolve().parents[2]
    with pytest.raises(ValidationError):
        Settings(
            _env_file=(root / ".env.base", root / ".env.test.base"),
            alert_channel_priority="   ",
        )
