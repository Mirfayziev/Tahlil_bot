"""app/media.py — Telegram fayl proksi route testlari."""
from unittest.mock import patch

from tests.conftest import login


def test_telegram_file_requires_login(client, service_request, db):
    from app.models import RequestAttachment
    att = RequestAttachment(request_id=service_request.id, file_type="photo",
                             file_ref="fake-file-id", stage="murojaat",
                             uploaded_by_type="customer", uploaded_by_id=1)
    db.session.add(att)
    db.session.commit()

    resp = client.get(f"/media/telegram/{att.id}")
    assert resp.status_code in (302, 401)


def test_telegram_file_streams_image_with_guessed_content_type(client, super_admin, service_request, db):
    from app.models import RequestAttachment
    att = RequestAttachment(request_id=service_request.id, file_type="photo",
                             file_ref="fake-file-id", stage="murojaat",
                             uploaded_by_type="customer", uploaded_by_id=1)
    db.session.add(att)
    db.session.commit()

    login(client, "test_admin", "AdminPass123")

    with patch("app.media.download_telegram_file", return_value=(b"jpeg-bytes", "application/octet-stream")):
        resp = client.get(f"/media/telegram/{att.id}")

    assert resp.status_code == 200
    assert resp.mimetype == "image/jpeg"
    assert resp.data == b"jpeg-bytes"


def test_telegram_file_not_found_returns_404(client, super_admin):
    login(client, "test_admin", "AdminPass123")
    resp = client.get("/media/telegram/99999")
    assert resp.status_code == 404


def test_telegram_file_download_failure_returns_404(client, super_admin, service_request, db):
    from app.models import RequestAttachment
    att = RequestAttachment(request_id=service_request.id, file_type="photo",
                             file_ref="fake-file-id", stage="murojaat",
                             uploaded_by_type="customer", uploaded_by_id=1)
    db.session.add(att)
    db.session.commit()

    login(client, "test_admin", "AdminPass123")

    with patch("app.media.download_telegram_file", return_value=(None, None)):
        resp = client.get(f"/media/telegram/{att.id}")

    assert resp.status_code == 404
