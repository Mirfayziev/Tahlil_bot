"""Dispetcher — murojaatlarni bo'lim/bino bo'yicha ijrochilarga tayinlash testlari.

Bular ilovaning eng muhim biznes-mantig'ini tekshiradi: ijrochi faqat o'zi
biriktirilgan bo'lim VA binodagi murojaatlarga tayinlanishi mumkin.
"""
from tests.conftest import login
from app.models import User, RoleEnum, Department, Building, RequestAssignment, RequestStatus


def _accept(client, req_id):
    return client.post(f"/dispatcher/requests/{req_id}/accept", follow_redirects=True)


def test_accept_request(client, super_admin, service_request, db):
    login(client, "test_admin", "AdminPass123")
    resp = _accept(client, service_request.id)
    assert resp.status_code == 200
    db.session.refresh(service_request)
    assert service_request.status == RequestStatus.ACCEPTED


def test_only_matching_executor_shown_in_assign_list(client, super_admin, executor_user,
                                                       service_request, department, building, db):
    """Boshqa bo'lim/binodagi ijrochi ro'yxatda ko'rinmasligi kerak."""
    other_dept = Department(name="Boshqa bo'lim 2")
    other_building = Building(name="Boshqa bino 2")
    db.session.add_all([other_dept, other_building])
    db.session.commit()

    unrelated_executor = User(full_name="Aloqasiz ijrochi", username="unrelated_exec",
                               role=RoleEnum.EXECUTOR)
    unrelated_executor.set_password("Pass12345")
    unrelated_executor.departments = [other_dept]
    unrelated_executor.buildings = [other_building]
    db.session.add(unrelated_executor)
    db.session.commit()

    login(client, "test_admin", "AdminPass123")
    _accept(client, service_request.id)

    resp = client.get(f"/dispatcher/requests/{service_request.id}")
    assert executor_user.full_name.encode() in resp.data
    assert unrelated_executor.full_name.encode() not in resp.data


def test_assign_to_matching_executor_succeeds(client, super_admin, executor_user, service_request, db):
    login(client, "test_admin", "AdminPass123")
    _accept(client, service_request.id)

    resp = client.post(f"/dispatcher/requests/{service_request.id}/assign", data={
        "executor_ids": [str(executor_user.id)],
    }, follow_redirects=True)
    assert resp.status_code == 200

    assignment = RequestAssignment.query.filter_by(request_id=service_request.id).first()
    assert assignment is not None
    assert assignment.executor_id == executor_user.id


def test_assign_to_mismatched_executor_rejected(client, super_admin, service_request, db):
    """Boshqa bo'lim/binodagi ijrochiga tayinlashga urinish server tomonida rad etilishi kerak
    (hatto UI'dagi tanlov ro'yxati chetlab o'tilsa ham)."""
    other_dept = Department(name="Mos kelmaydigan bo'lim")
    db.session.add(other_dept)
    db.session.commit()

    mismatched_executor = User(full_name="Mos kelmaydi", username="mismatched_exec",
                                role=RoleEnum.EXECUTOR)
    mismatched_executor.set_password("Pass12345")
    mismatched_executor.departments = [other_dept]
    db.session.add(mismatched_executor)
    db.session.commit()

    login(client, "test_admin", "AdminPass123")
    _accept(client, service_request.id)

    resp = client.post(f"/dispatcher/requests/{service_request.id}/assign", data={
        "executor_ids": [str(mismatched_executor.id)],
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"biriktirilmagan" in resp.data

    assignment = RequestAssignment.query.filter_by(request_id=service_request.id).first()
    assert assignment is None


def test_reject_request(client, super_admin, service_request, db):
    login(client, "test_admin", "AdminPass123")
    resp = client.post(f"/dispatcher/requests/{service_request.id}/reject",
                        data={"reason": "Test sababi"}, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(service_request)
    assert service_request.status == RequestStatus.REJECTED
    assert service_request.reject_reason == "Test sababi"
