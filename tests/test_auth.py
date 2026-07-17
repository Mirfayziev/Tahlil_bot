"""Autentifikatsiya va login himoyasi testlari."""
from tests.conftest import TestConfig, login
from app import create_app
from app.extensions import db as _db
from app.models import User, RoleEnum, AuditLog


def test_login_success(client, super_admin):
    resp = login(client, "test_admin", "AdminPass123")
    assert resp.status_code == 200
    assert "Boshqaruv paneli".encode() in resp.data or b"dashboard" in resp.data.lower()


def test_login_wrong_password(client, super_admin):
    resp = login(client, "test_admin", "wrong-password")
    assert b"flash-danger" in resp.data
    assert "noto".encode() in resp.data


def test_login_creates_audit_log(client, super_admin, db):
    login(client, "test_admin", "AdminPass123")
    logs = AuditLog.query.filter_by(user_id=super_admin.id, action="login_success").all()
    assert len(logs) == 1


def test_login_lockout_after_max_attempts(client, super_admin, app):
    max_attempts = app.config["LOGIN_MAX_ATTEMPTS"]
    for _ in range(max_attempts - 1):
        login(client, "test_admin", "wrong-password")

    resp = login(client, "test_admin", "wrong-password")
    assert "bloklandi".encode() in resp.data

    resp = login(client, "test_admin", "AdminPass123")
    assert "bloklangan".encode() in resp.data


def test_logout_requires_login(client):
    resp = client.get("/logout", follow_redirects=True)
    assert b"Kirish" in resp.data or "tizimga kiring".encode() in resp.data


def test_csrf_blocks_request_without_token():
    """CSRF himoyasi haqiqatan yoqilgan bo'lsa, token'siz POST rad etilishi kerak."""
    class CsrfEnabledConfig(TestConfig):
        WTF_CSRF_ENABLED = True

    app = create_app(CsrfEnabledConfig)
    with app.app_context():
        _db.create_all()
        u = User(full_name="Csrf Test", username="csrf_test", role=RoleEnum.SUPER_ADMIN)
        u.set_password("CsrfPass123")
        _db.session.add(u)
        _db.session.commit()

        client = app.test_client()
        resp = client.post("/login", data={"username": "csrf_test", "password": "CsrfPass123"})
        assert resp.status_code == 400

        _db.session.remove()
        _db.drop_all()
