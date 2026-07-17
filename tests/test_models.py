"""Model darajasidagi unit testlar."""
from datetime import datetime, timedelta

from app.models import RequestStatus, Priority


def test_password_hashing(super_admin):
    assert super_admin.check_password("AdminPass123")
    assert not super_admin.check_password("wrong-password")
    assert super_admin.password_hash != "AdminPass123"


def test_user_is_locked_property(super_admin, db):
    assert super_admin.is_locked is False
    super_admin.locked_until = datetime.utcnow() + timedelta(minutes=10)
    db.session.commit()
    assert super_admin.is_locked is True
    super_admin.locked_until = datetime.utcnow() - timedelta(minutes=10)
    db.session.commit()
    assert super_admin.is_locked is False


def test_service_request_org_display(service_request):
    service_request.org_department = "Moliya"
    service_request.org_division = "Hisob-kitob"
    service_request.room_number = "215"
    assert "Moliya" in service_request.org_display
    assert "Hisob-kitob" in service_request.org_display
    assert "215" in service_request.org_display


def test_service_request_org_display_independent(service_request):
    service_request.org_is_independent = True
    service_request.org_division = "Kadrlar boshqarmasi"
    assert "Mustaqil boshqarma" in service_request.org_display
    assert "Kadrlar boshqarmasi" in service_request.org_display


def test_is_overdue_false_without_deadline(service_request):
    assert service_request.is_overdue is False


def test_is_overdue_true_when_past_deadline(service_request, db):
    service_request.deadline_at = datetime.utcnow() - timedelta(hours=1)
    db.session.commit()
    assert service_request.is_overdue is True


def test_is_overdue_false_when_closed(service_request, db):
    service_request.deadline_at = datetime.utcnow() - timedelta(hours=1)
    service_request.status = RequestStatus.CLOSED
    db.session.commit()
    assert service_request.is_overdue is False


def test_executor_multi_department_and_building(executor_user, department, building):
    assert department in executor_user.departments
    assert building in executor_user.buildings
    assert len(executor_user.departments) == 1
    assert len(executor_user.buildings) == 1
