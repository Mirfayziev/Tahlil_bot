"""app/notify.py testlari (haqiqiy Telegram API'ga so'rov yubormasdan, mock bilan)."""
from unittest.mock import patch

from app.notify import send_telegram_message, send_telegram_photo, download_telegram_file, notify
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


def test_download_telegram_file_success():
    class FakeGetFileResp:
        status_code = 200

        def json(self):
            return {"result": {"file_path": "photos/file_0.jpg"}}

    class FakeDownloadResp:
        status_code = 200
        content = b"binary-image-bytes"
        headers = {"Content-Type": "image/jpeg"}

    with patch("requests.get", side_effect=[FakeGetFileResp(), FakeDownloadResp()]):
        content, content_type = download_telegram_file("fake-token", "file-id-123")
    assert content == b"binary-image-bytes"
    assert content_type == "image/jpeg"


def test_download_telegram_file_no_token_returns_none():
    assert download_telegram_file("", "file-id") == (None, None)


def test_send_telegram_photo_same_bot_uses_file_id_directly():
    class FakeResp:
        status_code = 200
        text = "ok"

    with patch("requests.post", return_value=FakeResp()) as mock_post:
        ok = send_telegram_photo("token-a", "12345", "file-id-1", caption="salom", source_token="token-a")
    assert ok is True
    assert "sendPhoto" in mock_post.call_args[0][0]
    assert mock_post.call_args[1]["json"]["photo"] == "file-id-1"


def test_send_telegram_photo_cross_bot_downloads_and_reuploads():
    class FakeGetFileResp:
        status_code = 200

        def json(self):
            return {"result": {"file_path": "photos/file_0.jpg"}}

    class FakeDownloadResp:
        status_code = 200
        content = b"raw-bytes"
        headers = {"Content-Type": "image/jpeg"}

    class FakeUploadResp:
        status_code = 200
        text = "ok"

    with patch("requests.get", side_effect=[FakeGetFileResp(), FakeDownloadResp()]), \
         patch("requests.post", return_value=FakeUploadResp()) as mock_post:
        ok = send_telegram_photo("executor-token", "999", "customer-file-id",
                                  caption="yangi topshiriq", source_token="customer-token")
    assert ok is True
    assert "executor-token" in mock_post.call_args[0][0]
    assert mock_post.call_args[1]["files"]["photo"][1] == b"raw-bytes"


def test_send_telegram_photo_cross_bot_download_failure_returns_false():
    class FakeGetFileResp:
        status_code = 400

        def json(self):
            return {}

    with patch("requests.get", return_value=FakeGetFileResp()):
        ok = send_telegram_photo("executor-token", "999", "bad-file-id", source_token="customer-token")
    assert ok is False


def test_notify_executor_with_photo_sends_photo_not_text(app, db):
    from app.models import User, RoleEnum
    app.config["EXECUTOR_BOT_TOKEN"] = "exec-token"
    app.config["CUSTOMER_BOT_TOKEN"] = "cust-token"
    executor = User(full_name="Rasm Ijrochi", username="photo_exec", role=RoleEnum.EXECUTOR,
                     telegram_id="555666777")
    executor.set_password("Pass12345")
    db.session.add(executor)
    db.session.commit()

    class FakeGetFileResp:
        status_code = 200

        def json(self):
            return {"result": {"file_path": "photos/file_0.jpg"}}

    class FakeDownloadResp:
        status_code = 200
        content = b"raw-bytes"
        headers = {"Content-Type": "image/jpeg"}

    class FakeUploadResp:
        status_code = 200
        text = "ok"

    with patch("requests.get", side_effect=[FakeGetFileResp(), FakeDownloadResp()]), \
         patch("requests.post", return_value=FakeUploadResp()) as mock_post:
        notif = notify("executor", executor.id, "Yangi topshiriq", photo_file_id="some-file-id")
    db.session.commit()

    assert notif.is_sent is True
    assert "sendPhoto" in mock_post.call_args[0][0]
