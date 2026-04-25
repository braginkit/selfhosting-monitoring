from __future__ import annotations

from pathlib import Path

import yaml

from monitoring.models import Target


def load_targets(path: Path) -> list[Target]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = raw.get("targets", [])
    targets: list[Target] = []
    for item in items:
        targets.append(
            Target(
                name=item["name"],
                type=item["type"],
                timeout_seconds=int(item.get("timeout_seconds", 10)),
                url=item.get("url"),
                host=item.get("host"),
                port=item.get("port"),
                query=item.get("query"),
            )
        )
    return targets
