from __future__ import annotations

import aiosmtplib
import dns.asyncresolver
from aiohttp import ClientSession, ClientTimeout

from monitoring.models import Target


async def check_http(target: Target) -> tuple[bool, str]:
    if not target.url:
        return False, "Missing url for HTTP target"
    timeout = ClientTimeout(total=target.timeout_seconds)
    try:
        async with ClientSession(timeout=timeout) as session:
            async with session.get(target.url) as response:
                if 200 <= response.status < 400:
                    return True, f"HTTP {response.status}"
                return False, f"HTTP {response.status}"
    except Exception as exc:
        return False, f"HTTP error: {exc}"


async def check_smtp(target: Target) -> tuple[bool, str]:
    if not target.host or not target.port:
        return False, "Missing host/port for SMTP target"
    try:
        client = aiosmtplib.SMTP(
            hostname=target.host, port=target.port, timeout=target.timeout_seconds
        )
        await client.connect()
        await client.quit()
        return True, "SMTP connect ok"
    except Exception as exc:
        return False, f"SMTP error: {exc}"


async def check_dns(target: Target) -> tuple[bool, str]:
    if not target.host or not target.query:
        return False, "Missing host/query for DNS target"
    resolver = dns.asyncresolver.Resolver(configure=False)
    resolver.nameservers = [target.host]
    resolver.timeout = target.timeout_seconds
    resolver.lifetime = target.timeout_seconds
    try:
        answer = await resolver.resolve(target.query, "A")
        if len(answer) > 0:
            return True, "DNS resolve ok"
        return False, "DNS empty response"
    except Exception as exc:
        return False, f"DNS error: {exc}"
