"""Admin panel (kategoriyalar, xodimlar, bo'limlar, binolar) testlari."""
from tests.conftest import login
from app.models import Department, Building, User, ServiceCategory


def test_non_admin_cannot_access_staff_page(client, dispatcher_user):
    login(client, "test_dispatcher", "DispatchPass123")
    resp = client.get("/admin/staff")
    assert resp.status_code == 403


def test_admin_can_create_department(client, super_admin, db):
    login(client, "test_admin", "AdminPass123")
    resp = client.post("/admin/departments", data={"name": "Yangi bo'lim", "description": "desc"},
                        follow_redirects=True)
    assert resp.status_code == 200
    assert Department.query.filter_by(name="Yangi bo'lim").first() is not None


def test_admin_can_create_building(client, super_admin, db):
    login(client, "test_admin", "AdminPass123")
    resp = client.post("/admin/buildings", data={"name": "Yangi bino"}, follow_redirects=True)
    assert resp.status_code == 200
    assert Building.query.filter_by(name="Yangi bino").first() is not None


def test_duplicate_department_name_rejected(client, super_admin, department, db):
    login(client, "test_admin", "AdminPass123")
    resp = client.post("/admin/departments", data={"name": department.name.upper()},
                        follow_redirects=True)
    assert resp.status_code == 200
    assert Department.query.filter_by(name=department.name).count() == 1


def test_duplicate_building_name_rejected(client, super_admin, building, db):
    login(client, "test_admin", "AdminPass123")
    resp = client.post("/admin/buildings", data={"name": building.name.lower()},
                        follow_redirects=True)
    assert resp.status_code == 200
    assert Building.query.filter_by(name=building.name).count() == 1


def test_delete_department_unlinks_category_and_user(client, super_admin, department, category, executor_user, db):
    login(client, "test_admin", "AdminPass123")
    category.department_id = department.id
    executor_user.department_id = department.id
    executor_user.departments = [department]
    db.session.commit()

    resp = client.post(f"/admin/departments/{department.id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert Department.query.get(department.id) is None

    db.session.refresh(category)
    db.session.refresh(executor_user)
    assert category.department_id is None
    assert executor_user.department_id is None
    assert executor_user.departments == []


def test_delete_building_unlinks_request(client, super_admin, building, service_request, db):
    login(client, "test_admin", "AdminPass123")
    service_request.building_id = building.id
    db.session.commit()

    resp = client.post(f"/admin/buildings/{building.id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert Building.query.get(building.id) is None

    db.session.refresh(service_request)
    assert service_request.building_id is None


def test_weak_password_rejected_on_staff_creation(client, super_admin, db):
    login(client, "test_admin", "AdminPass123")
    resp = client.post("/admin/staff", data={
        "full_name": "Weak Pass", "username": "weakpass_user", "password": "weak",
        "role": "ijrochi",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert User.query.filter_by(username="weakpass_user").first() is None


def test_strong_password_accepted_on_staff_creation(client, super_admin, db):
    login(client, "test_admin", "AdminPass123")
    resp = client.post("/admin/staff", data={
        "full_name": "Strong Pass", "username": "strongpass_user", "password": "StrongPass123",
        "role": "ijrochi",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert User.query.filter_by(username="strongpass_user").first() is not None


def test_executor_multi_department_assignment(client, super_admin, executor_user, department, db):
    second_dept = Department(name="Ikkinchi bo'lim")
    db.session.add(second_dept)
    db.session.commit()

    login(client, "test_admin", "AdminPass123")
    resp = client.post(f"/admin/staff/{executor_user.id}/set-departments", data={
        "department_ids": [str(department.id), str(second_dept.id)],
    }, follow_redirects=True)
    assert resp.status_code == 200

    db.session.refresh(executor_user)
    assert len(executor_user.departments) == 2


def test_category_department_link(client, super_admin, category, department, db):
    other_dept = Department(name="Boshqa bo'lim")
    db.session.add(other_dept)
    db.session.commit()

    login(client, "test_admin", "AdminPass123")
    resp = client.post(f"/admin/categories/{category.id}/set-department", data={
        "department_id": str(other_dept.id),
    }, follow_redirects=True)
    assert resp.status_code == 200

    db.session.refresh(category)
    assert category.department_id == other_dept.id
