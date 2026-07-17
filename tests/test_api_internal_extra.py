"""Ichki bot API'sining qolgan endpointlari uchun qo'shimcha testlar."""
from app.models import RequestAssignment, Rating


def _headers(app):
    return {"X-Internal-Token": app.config["INTERNAL_API_TOKEN"], "Content-Type": "application/json"}


def test_get_request_detail(client, app, service_request):
    resp = client.get(f"/api/requests/{service_request.id}", headers=_headers(app))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["number"] == service_request.number
    assert "status_logs" in data


def test_list_customer_requests(client, app, customer, service_request):
    resp = client.get(f"/api/requests/customer/{customer.telegram_id}", headers=_headers(app))
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(r["number"] == service_request.number for r in data)


def test_list_customer_requests_unknown_customer(client, app):
    resp = client.get("/api/requests/customer/does-not-exist", headers=_headers(app))
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_respond_assignment_accept(client, app, executor_user, service_request, db):
    assignment = RequestAssignment(request_id=service_request.id, executor_id=executor_user.id)
    db.session.add(assignment)
    db.session.commit()

    resp = client.post(f"/api/assignments/{assignment.id}/respond", json={
        "decision": "qabul_qilindi",
    }, headers=_headers(app))
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ijrochiga_yuborildi"


def test_respond_assignment_reject(client, app, executor_user, service_request, db):
    assignment = RequestAssignment(request_id=service_request.id, executor_id=executor_user.id)
    db.session.add(assignment)
    db.session.commit()

    resp = client.post(f"/api/assignments/{assignment.id}/respond", json={
        "decision": "rad_etildi", "reason": "band edim",
    }, headers=_headers(app))
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "qabul_qilindi"


def test_start_assignment(client, app, executor_user, service_request, db):
    assignment = RequestAssignment(request_id=service_request.id, executor_id=executor_user.id)
    db.session.add(assignment)
    db.session.commit()

    resp = client.post(f"/api/assignments/{assignment.id}/start", headers=_headers(app))
    assert resp.status_code == 200
    db.session.refresh(service_request)
    assert service_request.status.value == "bajarilmoqda"


def test_request_more_info(client, app, executor_user, service_request, db):
    assignment = RequestAssignment(request_id=service_request.id, executor_id=executor_user.id)
    db.session.add(assignment)
    db.session.commit()

    resp = client.post(f"/api/assignments/{assignment.id}/request-info", json={
        "question": "Qaysi qavatda?",
    }, headers=_headers(app))
    assert resp.status_code == 200
    db.session.refresh(service_request)
    assert service_request.status.value == "qoshimcha_malumot_kutilmoqda"


def test_extend_assignment(client, app, executor_user, service_request, db):
    assignment = RequestAssignment(request_id=service_request.id, executor_id=executor_user.id)
    db.session.add(assignment)
    db.session.commit()

    resp = client.post(f"/api/assignments/{assignment.id}/extend", json={
        "extra_hours": 4, "reason": "qo'shimcha qism kerak",
    }, headers=_headers(app))
    assert resp.status_code == 200
    assert "new_deadline" in resp.get_json()


def test_rate_request(client, app, service_request, db):
    from datetime import datetime
    service_request.status = service_request.status.__class__.DONE
    service_request.completed_at = datetime.utcnow()
    db.session.commit()

    resp = client.post(f"/api/requests/{service_request.id}/rate", json={
        "stars": 5, "comment": "Zo'r xizmat", "suggestion": None,
    }, headers=_headers(app))
    assert resp.status_code == 200
    assert Rating.query.filter_by(request_id=service_request.id).first() is not None


def test_rate_request_twice_rejected(client, app, service_request, db):
    resp1 = client.post(f"/api/requests/{service_request.id}/rate", json={"stars": 4},
                         headers=_headers(app))
    assert resp1.status_code == 200

    resp2 = client.post(f"/api/requests/{service_request.id}/rate", json={"stars": 2},
                         headers=_headers(app))
    assert resp2.status_code == 400


def test_list_categories(client, app, category):
    resp = client.get("/api/categories", headers=_headers(app))
    assert resp.status_code == 200
    assert any(c["name"] == category.name_uz for c in resp.get_json())


def test_list_departments(client, app, department):
    resp = client.get("/api/departments", headers=_headers(app))
    assert resp.status_code == 200
    assert any(d["name"] == department.name for d in resp.get_json())


def test_list_buildings(client, app, building):
    resp = client.get("/api/buildings", headers=_headers(app))
    assert resp.status_code == 200
    assert any(b["name"] == building.name for b in resp.get_json())
