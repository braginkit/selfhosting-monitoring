from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path

QUEUE_ID_RE = re.compile(r"\b([0-9A-F]{10,12}):\s")
QUEUED_AS_RE = re.compile(r"queued_as:\s*([0-9A-F]+)", re.IGNORECASE)
QUEUE_ID_FIELD_RE = re.compile(r"Queue-ID:\s*([0-9A-F]+)", re.IGNORECASE)
MESSAGE_ID_RE = re.compile(r"message-id=<([^>]+)>", re.IGNORECASE)
MESSAGE_ID_HEADER_RE = re.compile(r"Message-ID:\s*<([^>]+)>", re.IGNORECASE)
BOUNCED_RE = re.compile(r"status=bounced\b", re.IGNORECASE)
RELAY_SENT_RE = re.compile(
    r"relay=smtp\.mail\.me\.com.*\bdsn=2\.0\.0\b.*\bstatus=sent\b",
    re.IGNORECASE,
)
BAD_HEADER_RE = re.compile(r"Blocked BAD-HEADER", re.IGNORECASE)
ICLOUD_ISSUE_RE = re.compile(
    r"(spamhaus|smtp\.mail\.me\.com|icloud\.com|5\.7\.1|5\.7\.0)",
    re.IGNORECASE,
)


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    DEFERRED = "deferred"
    UNKNOWN = "unknown"


def _normalize_message_id(message_id: str) -> str:
    return message_id.strip().strip("<>").lower()


def _collect_queue_ids(log_text: str, message_id: str) -> set[str]:
    needle = _normalize_message_id(message_id)
    queue_ids: set[str] = set()
    for line in log_text.splitlines():
        line_ids: list[str] = []
        for pattern in (MESSAGE_ID_RE, MESSAGE_ID_HEADER_RE):
            match = pattern.search(line)
            if match and _normalize_message_id(match.group(1)) == needle:
                line_ids.append(needle)
        if needle in line.lower() or line_ids:
            q_match = QUEUE_ID_RE.search(line)
            if q_match:
                queue_ids.add(q_match.group(1))
            q_field = QUEUE_ID_FIELD_RE.search(line)
            if q_field:
                queue_ids.add(q_field.group(1))
    return queue_ids


def _expand_queue_ids(log_text: str, queue_ids: set[str]) -> set[str]:
    expanded = set(queue_ids)
    changed = True
    while changed:
        changed = False
        for line in log_text.splitlines():
            for queue_id in list(expanded):
                if queue_id not in line:
                    continue
                for pattern in (QUEUED_AS_RE, QUEUE_ID_FIELD_RE):
                    match = pattern.search(line)
                    if match and match.group(1) not in expanded:
                        expanded.add(match.group(1))
                        changed = True
    return expanded


def _lines_for_queues(log_text: str, queue_ids: set[str]) -> list[str]:
    if not queue_ids:
        return []
    lines: list[str] = []
    for line in log_text.splitlines():
        for queue_id in queue_ids:
            if line.startswith(queue_id) or f" {queue_id}:" in line:
                lines.append(line)
                break
    return lines


def _extract_error_hint(lines: list[str]) -> str | None:
    for line in reversed(lines):
        if "status=bounced" in line.lower():
            bounced_idx = line.lower().find("status=bounced")
            return line[bounced_idx:].strip()
        if BAD_HEADER_RE.search(line):
            return line.strip()
    return None


def inspect_mail_logs(log_text: str, message_id: str) -> tuple[DeliveryStatus, str | None]:
    """Classify delivery outcome for a Message-ID using merged mail log text."""
    if not log_text.strip():
        return DeliveryStatus.UNKNOWN, None

    queue_ids = _expand_queue_ids(log_text, _collect_queue_ids(log_text, message_id))
    related = _lines_for_queues(log_text, queue_ids)
    if not related and _normalize_message_id(message_id) not in log_text.lower():
        return DeliveryStatus.PENDING, None

    if not related:
        related = [
            line
            for line in log_text.splitlines()
            if _normalize_message_id(message_id) in line.lower()
        ]

    joined = "\n".join(related)

    if any(BOUNCED_RE.search(line) for line in related):
        return DeliveryStatus.BOUNCED, _extract_error_hint(related)

    if any(BAD_HEADER_RE.search(line) for line in related):
        return DeliveryStatus.BOUNCED, _extract_error_hint(related)

    if any(RELAY_SENT_RE.search(line) for line in related):
        return DeliveryStatus.DELIVERED, None

    if "status=deferred" in joined.lower():
        return DeliveryStatus.DEFERRED, _extract_error_hint(related)

    return DeliveryStatus.PENDING, None


def read_mail_log_files(log_dir: Path, *, max_bytes_per_file: int = 2_000_000) -> str:
    if not log_dir.is_dir():
        return ""

    chunks: list[str] = []
    for path in sorted(log_dir.glob("*.log")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if len(data) > max_bytes_per_file:
            data = data[-max_bytes_per_file:]
        chunks.append(data.decode("utf-8", errors="replace"))
    return "\n".join(chunks)
