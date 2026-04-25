import pytest

from monitoring.checks.types import check_dns, check_http, check_smtp
from monitoring.models import Target


class _FakeHttpResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    async def __aenter__(self) -> "_FakeHttpResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeHttpSession:
    def __init__(self, status: int) -> None:
        self._status = status

    async def __aenter__(self) -> "_FakeHttpSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url: str) -> _FakeHttpResponse:
        return _FakeHttpResponse(self._status)


@pytest.mark.asyncio
async def test_check_http_missing_url() -> None:
    ok, reason = await check_http(Target(name="svc", type="http"))
    assert ok is False
    assert "Missing url" in reason


@pytest.mark.asyncio
async def test_check_http_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("monitoring.checks.types.ClientSession", lambda timeout: _FakeHttpSession(200))
    ok, reason = await check_http(Target(name="svc", type="http", url="https://example.invalid"))
    assert ok is True
    assert reason == "HTTP 200"


@pytest.mark.asyncio
async def test_check_http_non_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("monitoring.checks.types.ClientSession", lambda timeout: _FakeHttpSession(503))
    ok, reason = await check_http(Target(name="svc", type="http", url="https://example.invalid"))
    assert ok is False
    assert reason == "HTTP 503"


@pytest.mark.asyncio
async def test_check_http_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(timeout):
        raise RuntimeError("network down")

    monkeypatch.setattr("monitoring.checks.types.ClientSession", _boom)
    ok, reason = await check_http(Target(name="svc", type="http", url="https://example.invalid"))
    assert ok is False
    assert "HTTP error" in reason


class _FakeSmtpClient:
    async def connect(self) -> None:
        return None

    async def quit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_check_smtp_missing_host_port() -> None:
    ok, reason = await check_smtp(Target(name="svc", type="smtp"))
    assert ok is False
    assert "Missing host/port" in reason


@pytest.mark.asyncio
async def test_check_smtp_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("monitoring.checks.types.aiosmtplib.SMTP", lambda **kwargs: _FakeSmtpClient())
    ok, reason = await check_smtp(Target(name="svc", type="smtp", host="smtp.example.invalid", port=587))
    assert ok is True
    assert reason == "SMTP connect ok"


@pytest.mark.asyncio
async def test_check_smtp_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(**kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr("monitoring.checks.types.aiosmtplib.SMTP", _boom)
    ok, reason = await check_smtp(Target(name="svc", type="smtp", host="smtp.example.invalid", port=587))
    assert ok is False
    assert "SMTP error" in reason


class _FakeResolver:
    def __init__(self, configure: bool) -> None:
        self.nameservers: list[str] = []
        self.timeout = 0
        self.lifetime = 0

    async def resolve(self, query: str, record_type: str):  # noqa: ANN001
        return ["1.1.1.1"]


class _FakeResolverEmpty(_FakeResolver):
    async def resolve(self, query: str, record_type: str):  # noqa: ANN001
        return []


@pytest.mark.asyncio
async def test_check_dns_missing_host_query() -> None:
    ok, reason = await check_dns(Target(name="svc", type="dns"))
    assert ok is False
    assert "Missing host/query" in reason


@pytest.mark.asyncio
async def test_check_dns_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("monitoring.checks.types.dns.asyncresolver.Resolver", _FakeResolver)
    ok, reason = await check_dns(Target(name="svc", type="dns", host="127.0.0.1", query="example.invalid"))
    assert ok is True
    assert reason == "DNS resolve ok"


@pytest.mark.asyncio
async def test_check_dns_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("monitoring.checks.types.dns.asyncresolver.Resolver", _FakeResolverEmpty)
    ok, reason = await check_dns(Target(name="svc", type="dns", host="127.0.0.1", query="example.invalid"))
    assert ok is False
    assert reason == "DNS empty response"


@pytest.mark.asyncio
async def test_check_dns_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BoomResolver(_FakeResolver):
        async def resolve(self, query: str, record_type: str):  # noqa: ANN001
            raise RuntimeError("dns failed")

    monkeypatch.setattr("monitoring.checks.types.dns.asyncresolver.Resolver", _BoomResolver)
    ok, reason = await check_dns(Target(name="svc", type="dns", host="127.0.0.1", query="example.invalid"))
    assert ok is False
    assert "DNS error" in reason
