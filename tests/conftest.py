from pathlib import Path

import fakeredis.aioredis
import pytest

from monitoring.config import Settings


@pytest.fixture
async def fake_redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def fake_settings() -> Settings:
    root = Path(__file__).resolve().parents[1]
    return Settings(_env_file=(root / ".env.base", root / ".env.test.base"))
