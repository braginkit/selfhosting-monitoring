from datetime import UTC, datetime

import pytest

from monitoring.models import IncidentState
from monitoring.state.redis_state import RedisStateStore


@pytest.mark.asyncio
async def test_get_returns_default_up_state(fake_redis) -> None:
    store = RedisStateStore(fake_redis, "state_test")
    state = await store.get("matrix")

    assert state.status == "up"
    assert state.fail_count == 0


@pytest.mark.asyncio
async def test_save_and_get_roundtrip(fake_redis) -> None:
    store = RedisStateStore(fake_redis, "state_test")
    now = datetime.now(UTC)
    await store.save(
        IncidentState(
            target="hoppscotch",
            fail_count=3,
            status="down",
            first_failed_at=now,
            last_alert_at=now,
            last_failure_reason="HTTP 503",
        )
    )

    loaded = await store.get("hoppscotch")
    assert loaded.fail_count == 3
    assert loaded.status == "down"


@pytest.mark.asyncio
async def test_reset_removes_incident_key(fake_redis) -> None:
    store = RedisStateStore(fake_redis, "state_test")
    await store.save(
        IncidentState(
            target="auth",
            fail_count=1,
            status="down",
            first_failed_at=datetime.now(UTC),
            last_alert_at=None,
            last_failure_reason="timeout",
        )
    )

    await store.reset("auth")
    state = await store.get("auth")

    assert state.status == "up"
    assert state.fail_count == 0
