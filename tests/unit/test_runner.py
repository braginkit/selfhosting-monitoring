from datetime import UTC, datetime

import pytest

from monitoring.checks.runner import run_check
from monitoring.models import Target


@pytest.mark.asyncio
async def test_run_check_routes_http(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_check_http(target: Target) -> tuple[bool, str]:
        return True, "HTTP 200"

    monkeypatch.setattr("monitoring.checks.runner.check_http", fake_check_http)
    result = await run_check(Target(name="svc", type="http", url="https://example.invalid"))

    assert result.ok is True
    assert result.reason == "HTTP 200"
    assert result.target == "svc"
    assert result.checked_at <= datetime.now(UTC)


@pytest.mark.asyncio
async def test_run_check_routes_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_check_smtp(target: Target) -> tuple[bool, str]:
        return False, "SMTP 421"

    monkeypatch.setattr("monitoring.checks.runner.check_smtp", fake_check_smtp)
    result = await run_check(Target(name="svc", type="smtp", host="smtp.example.invalid", port=587))

    assert result.ok is False
    assert result.reason == "SMTP 421"


@pytest.mark.asyncio
async def test_run_check_routes_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_check_dns(target: Target) -> tuple[bool, str]:
        return True, "DNS resolve ok"

    monkeypatch.setattr("monitoring.checks.runner.check_dns", fake_check_dns)
    result = await run_check(
        Target(name="svc", type="dns", host="1.1.1.1", query="example.invalid")
    )

    assert result.ok is True
    assert result.reason == "DNS resolve ok"


@pytest.mark.asyncio
async def test_run_check_dns_validation_path() -> None:
    result = await run_check(Target(name="svc", type="dns"))
    assert result.target == "svc"
    assert result.ok is False


@pytest.mark.asyncio
async def test_run_check_unsupported_type() -> None:
    target = Target(name="legacy", type="http")
    object.__setattr__(target, "type", "unknown")

    result = await run_check(target)

    assert result.ok is False
    assert "Unsupported target type: unknown" in result.reason
