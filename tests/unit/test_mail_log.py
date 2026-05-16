from pathlib import Path

from monitoring.delivery.mail_log import DeliveryStatus, inspect_mail_logs, read_mail_log_files


def test_inspect_delivered_via_icloud_relay() -> None:
    log = Path(__file__).resolve().parents[1] / "fixtures" / "mail_logs" / "mail.log"
    text = log.read_text(encoding="utf-8")

    status, error = inspect_mail_logs(text, "<test-delivered@bragin.crazedns.ru>")

    assert status == DeliveryStatus.DELIVERED
    assert error is None


def test_inspect_bounced_with_spamhaus() -> None:
    log = Path(__file__).resolve().parents[1] / "fixtures" / "mail_logs" / "mail.log"
    text = log.read_text(encoding="utf-8")

    status, error = inspect_mail_logs(text, "<test-bounced@bragin.crazedns.ru>")

    assert status == DeliveryStatus.BOUNCED
    assert error is not None
    assert "status=bounced" in error.lower() or "bad-header" in error.lower()


def test_inspect_unknown_when_message_missing() -> None:
    status, error = inspect_mail_logs("unrelated log line", "<missing@bragin.crazedns.ru>")

    assert status == DeliveryStatus.PENDING
    assert error is None


def test_read_mail_log_files_from_fixture_dir() -> None:
    log_dir = Path(__file__).resolve().parents[1] / "fixtures" / "mail_logs"
    text = read_mail_log_files(log_dir)

    assert "test-delivered@bragin.crazedns.ru" in text
