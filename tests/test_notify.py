"""app/notify.py testlari (haqiqiy Telegram API'ga so'rov yubormasdan, mock bilan)."""
from unittest.mock import patch

from app.notify import send_telegram_message, notify
from app.models import Notification


def test_send_telegram_message_no_token_returns_false():
    assert send_telegram_message("", "12345", "salom") is False


def test_send_telegram_message_no_chat_id_returns_false():
    assert send_telegram_message("fake-token", "", "salom") is False


def test_send_telegram_message_success(monkeypatch):
    class FakeResp:
        status_code = 200
        text = "ok"

    with patch("requests.post", return_value=FakeResp()):
        assert send_telegram_message("fake-token", "12345", "salom") is True


def test_send_telegram_message_failure_response():
    class FakeResp:
        status_code = 400
        text = "Bad Request"

    with patch("requests.post", return_value=FakeResp()):
        assert send_telegram_message("fake-token", "12345", "salom") is False


def test_notify_creates_notification_record(app, customer, db):
    notify("customer", customer.id, "Test xabar")
    db.session.commit()
    notif = Notification.query.filter_by(recipient_type="customer", recipient_id=customer.id).first()
    assert notif is not None
    assert notif.message == "Test xabar"


def test_notify_unknown_recipient_type_does_not_crash(app, db):
    notif = notify("unknown_type", 999, "xabar")
    db.session.commit()
    assert notif.is_sent is False
