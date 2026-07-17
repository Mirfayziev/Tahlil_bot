"""Dashboard sahifalari va JSON API'lari — smoke testlar."""
from tests.conftest import login


def _as_admin(client, super_admin):
    login(client, "test_admin", "AdminPass123")


def test_dashboard_index_requires_login(client):
    resp = client.get("/", follow_redirects=True)
    assert b"Kirish" in resp.data or "tizimga kiring".encode() in resp.data


def test_dashboard_index_renders(client, super_admin, service_request):
    _as_admin(client, super_admin)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Boshqaruv paneli".encode() in resp.data


def test_ratings_page_renders(client, super_admin):
    _as_admin(client, super_admin)
    resp = client.get("/ratings")
    assert resp.status_code == 200


def test_summary_api(client, super_admin, service_request):
    _as_admin(client, super_admin)
    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] >= 1


def test_dynamics_api(client, super_admin, service_request):
    _as_admin(client, super_admin)
    resp = client.get("/api/dashboard/dynamics")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_top_categories_api(client, super_admin, service_request):
    _as_admin(client, super_admin)
    resp = client.get("/api/dashboard/top-categories")
    assert resp.status_code == 200


def test_sla_status_api(client, super_admin, service_request):
    _as_admin(client, super_admin)
    resp = client.get("/api/dashboard/sla-status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "on_time" in data and "overdue" in data


def test_department_breakdown_api_with_multi_dept_executor(client, super_admin, executor_user,
                                                             service_request, db):
    from app.models import RequestAssignment
    db.session.add(RequestAssignment(request_id=service_request.id, executor_id=executor_user.id))
    db.session.commit()

    _as_admin(client, super_admin)
    resp = client.get("/api/dashboard/department-breakdown")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(d["department"] == executor_user.departments[0].name for d in data)


def test_ai_auto_assign_status_api(client, super_admin):
    _as_admin(client, super_admin)
    resp = client.get("/api/dashboard/ai-auto-assign-status")
    assert resp.status_code == 200
