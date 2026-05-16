import pytest

from monitoring.delivery.mail_log import DeliveryStatus
from monitoring.delivery.store import SmtpDeliveryStore
from monitoring.models import AlertEvent


@pytest.mark.asyncio
async def test_register_and_get_delivery_record(fake_redis) -> None:
    store = SmtpDeliveryStore(fake_redis, "delivery_test")
    event = AlertEvent(target="matrix", severity="down", title="down", body="body")

    await store.register("<abc@bragin.crazedns.ru>", event)
    record = await store.get("<abc@bragin.crazedns.ru>")

    assert record is not None
    assert record.target == "matrix"
    assert record.status == DeliveryStatus.PENDING
    assert record.matrix_escalated is False


@pytest.mark.asyncio
async def test_update_status_removes_from_pending(fake_redis) -> None:
    store = SmtpDeliveryStore(fake_redis, "delivery_test")
    event = AlertEvent(target="matrix", severity="down", title="down", body="body")
    message_id = "<done@bragin.crazedns.ru>"

    await store.register(message_id, event)
    await store.update_status(message_id, DeliveryStatus.DELIVERED)

    pending = await store.list_pending()
    assert pending == []
