from __future__ import annotations

from datetime import UTC, datetime

from monitoring.checks.types import check_dns, check_http, check_smtp
from monitoring.models import CheckResult, Target


async def run_check(target: Target) -> CheckResult:
    if target.type == "http":
        ok, reason = await check_http(target)
    elif target.type == "smtp":
        ok, reason = await check_smtp(target)
    elif target.type == "dns":
        ok, reason = await check_dns(target)
    else:
        ok, reason = False, f"Unsupported target type: {target.type}"

    return CheckResult(
        target=target.name,
        ok=ok,
        reason=reason,
        checked_at=datetime.now(UTC),
    )
