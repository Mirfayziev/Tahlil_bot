"""Botlar uchun ichki API (X-Internal-Token bilan himoyalangan) testlari."""
import json

from app.models import ServiceRequest, Customer, RequestAssignment


def _headers(app):
    return {"X-Internal-Token": app.config["INTERNAL_API_TOKEN"], "Content-Type": "application/json"}


def test_internal_api_requires_token(client):
    resp = client.post("/api/customers", json={"telegram_id": "123"})
    assert resp.status_code == 401


def test_upsert_customer(client, app):
    resp = client.post("/api/customers", json={
        "telegram_id": "555666777", "full_name": "API Mijoz", "phone": "998901112233",
    }, headers=_headers(app))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["telegram_id"] == "555666777"
    assert Customer.query.filter_by(telegram_id="555666777").first() is not None


def test_create_request_via_bot_api(client, app, category, building):
    client.post("/api/customers", json={"telegram_id": "555666888", "full_name": "Mijoz 2"},
                headers=_headers(app))

    resp = client.post("/api/requests", json={
        "telegram_id": "555666888", "category_id": category.id, "building_id": building.id,
        "description": "API orqali test murojaat",
    }, headers=_headers(app))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "yangi"

    req = ServiceRequest.query.filter_by(number=data["number"]).first()
    assert req is not None
    assert req.building_id == building.id


def test_create_request_unknown_customer_returns_404(client, app, category):
    resp = client.post("/api/requests", json={
        "telegram_id": "does-not-exist", "category_id": category.id, "description": "x",
    }, headers=_headers(app))
    assert resp.status_code == 404


def test_executor_tasks_only_shows_own_assignments(client, app, executor_user, service_request, db):
    other_executor = executor_user.__class__(full_name="Boshqa ijrochi", username="other_exec",
                                               role=executor_user.role, telegram_id="000111222")
    other_executor.set_password("Pass12345")
    db.session.add(other_executor)
    db.session.add(RequestAssignment(request_id=service_request.id, executor_id=executor_user.id))
    db.session.commit()

    resp = client.get(f"/api/executors/{executor_user.telegram_id}/tasks", headers=_headers(app))
    assert resp.status_code == 200
    tasks = resp.get_json()
    assert len(tasks) == 1
    assert tasks[0]["number"] == service_request.number

    resp2 = client.get(f"/api/executors/{other_executor.telegram_id}/tasks", headers=_headers(app))
    assert resp2.status_code == 200
    assert resp2.get_json() == []


def test_complete_assignment_marks_request_done(client, app, executor_user, service_request, db):
    assignment = RequestAssignment(request_id=service_request.id, executor_id=executor_user.id)
    db.session.add(assignment)
    db.session.commit()

    resp = client.post(f"/api/assignments/{assignment.id}/complete", json={
        "report_text": "Ish bajarildi", "time_spent_minutes": 30,
    }, headers=_headers(app))
    assert resp.status_code == 200

    db.session.refresh(service_request)
    assert service_request.status.value == "bajarildi"
