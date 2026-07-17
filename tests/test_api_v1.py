"""Versiyalangan JWT API (/api/v1) testlari."""
from app.models import RequestAssignment


def _login_v1(client, username, password):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_v1_login_success(client, super_admin):
    resp = _login_v1(client, "test_admin", "AdminPass123")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["role"] == "super_admin"


def test_v1_login_wrong_password(client, super_admin):
    resp = _login_v1(client, "test_admin", "wrong")
    assert resp.status_code == 401


def test_v1_login_missing_field_returns_422(client):
    resp = client.post("/api/v1/auth/login", json={"username": "x"})
    assert resp.status_code == 422
    assert "password" in resp.get_json()["errors"]


def test_v1_me_requires_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_v1_me_with_valid_token(client, super_admin):
    token = _login_v1(client, "test_admin", "AdminPass123").get_json()["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["username"] == "test_admin"


def test_v1_refresh_token_issues_new_access_token(client, super_admin):
    refresh_token = _login_v1(client, "test_admin", "AdminPass123").get_json()["refresh_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()


def test_v1_requests_list(client, super_admin, service_request):
    token = _login_v1(client, "test_admin", "AdminPass123").get_json()["access_token"]
    resp = client.get("/api/v1/requests", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] >= 1
    assert any(item["number"] == service_request.number for item in data["items"])


def test_v1_my_tasks_forbidden_for_non_executor(client, super_admin):
    token = _login_v1(client, "test_admin", "AdminPass123").get_json()["access_token"]
    resp = client.get("/api/v1/my-tasks", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_v1_my_tasks_for_executor(client, executor_user, service_request, db):
    db.session.add(RequestAssignment(request_id=service_request.id, executor_id=executor_user.id))
    db.session.commit()

    token = _login_v1(client, "test_executor", "ExecPass123").get_json()["access_token"]
    resp = client.get("/api/v1/my-tasks", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert len(tasks) == 1
    assert tasks[0]["request"]["number"] == service_request.number


def test_v1_complete_assignment_forbidden_for_other_executor(client, executor_user, service_request, db):
    from app.models import User, RoleEnum
    other = User(full_name="Boshqa", username="v1_other_exec", role=RoleEnum.EXECUTOR)
    other.set_password("Pass12345")
    db.session.add(other)
    assignment = RequestAssignment(request_id=service_request.id, executor_id=executor_user.id)
    db.session.add(assignment)
    db.session.commit()

    token = _login_v1(client, "v1_other_exec", "Pass12345").get_json()["access_token"]
    resp = client.post(f"/api/v1/assignments/{assignment.id}/complete",
                        json={"report_text": "urinish"},
                        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
