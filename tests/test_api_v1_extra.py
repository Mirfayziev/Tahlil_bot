"""v1 API — respond/complete endpointlari uchun qo'shimcha testlar."""
from app.models import RequestAssignment


def _login_v1(client, username, password):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password}).get_json()


def test_v1_respond_assignment_accept(client, executor_user, service_request, db):
    assignment = RequestAssignment(request_id=service_request.id, executor_id=executor_user.id)
    db.session.add(assignment)
    db.session.commit()

    token = _login_v1(client, "test_executor", "ExecPass123")["access_token"]
    resp = client.post(f"/api/v1/assignments/{assignment.id}/respond",
                        json={"decision": "qabul_qilindi"},
                        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ijrochiga_yuborildi"


def test_v1_respond_assignment_forbidden_for_other_executor(client, executor_user, service_request, db):
    from app.models import User, RoleEnum
    other = User(full_name="Boshqa 2", username="v1_other_exec_2", role=RoleEnum.EXECUTOR)
    other.set_password("Pass12345")
    db.session.add(other)
    assignment = RequestAssignment(request_id=service_request.id, executor_id=executor_user.id)
    db.session.add(assignment)
    db.session.commit()

    token = _login_v1(client, "v1_other_exec_2", "Pass12345")["access_token"]
    resp = client.post(f"/api/v1/assignments/{assignment.id}/respond",
                        json={"decision": "qabul_qilindi"},
                        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_v1_respond_assignment_validation_error(client, executor_user, service_request, db):
    assignment = RequestAssignment(request_id=service_request.id, executor_id=executor_user.id)
    db.session.add(assignment)
    db.session.commit()

    token = _login_v1(client, "test_executor", "ExecPass123")["access_token"]
    resp = client.post(f"/api/v1/assignments/{assignment.id}/respond",
                        json={"decision": "invalid_choice"},
                        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422


def test_v1_complete_assignment_success(client, executor_user, service_request, db):
    assignment = RequestAssignment(request_id=service_request.id, executor_id=executor_user.id)
    db.session.add(assignment)
    db.session.commit()

    token = _login_v1(client, "test_executor", "ExecPass123")["access_token"]
    resp = client.post(f"/api/v1/assignments/{assignment.id}/complete",
                        json={"report_text": "Bajarildi", "time_spent_minutes": 45},
                        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    db.session.refresh(service_request)
    assert service_request.status.value == "bajarildi"


def test_v1_complete_assignment_validation_error(client, executor_user, service_request, db):
    assignment = RequestAssignment(request_id=service_request.id, executor_id=executor_user.id)
    db.session.add(assignment)
    db.session.commit()

    token = _login_v1(client, "test_executor", "ExecPass123")["access_token"]
    resp = client.post(f"/api/v1/assignments/{assignment.id}/complete",
                        json={},
                        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422


def test_v1_get_request_detail(client, super_admin, service_request):
    token = _login_v1(client, "test_admin", "AdminPass123")["access_token"]
    resp = client.get(f"/api/v1/requests/{service_request.id}",
                       headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["number"] == service_request.number


def test_v1_requests_list_scoped_to_executor(client, executor_user, service_request, db):
    token = _login_v1(client, "test_executor", "ExecPass123")["access_token"]
    resp = client.get("/api/v1/requests", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["total"] == 0  # hali tayinlanmagan

    db.session.add(RequestAssignment(request_id=service_request.id, executor_id=executor_user.id))
    db.session.commit()

    resp2 = client.get("/api/v1/requests", headers={"Authorization": f"Bearer {token}"})
    assert resp2.get_json()["total"] == 1
