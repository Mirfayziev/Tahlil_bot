import pytest

from config import Config
from app import create_app
from app.extensions import db as _db
from app.models import (
    User, RoleEnum, Department, Building, ServiceCategory, Customer,
    ServiceRequest, RequestStatus, Priority,
)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    INTERNAL_API_TOKEN = "test-internal-token"
    JWT_SECRET_KEY = "test-jwt-secret-key-not-for-prod"
    CUSTOMER_BOT_TOKEN = ""
    EXECUTOR_BOT_TOKEN = ""
    NOTIFY_BOT_TOKEN = ""
    AUTO_ASSIGN_ENABLED = True
    AUTO_ASSIGN_AFTER_MINUTES = 15
    CACHE_TYPE = "SimpleCache"


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def super_admin(db):
    u = User(full_name="Test Admin", username="test_admin", role=RoleEnum.SUPER_ADMIN)
    u.set_password("AdminPass123")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def dispatcher_user(db):
    u = User(full_name="Test Dispatcher", username="test_dispatcher", role=RoleEnum.DISPATCHER)
    u.set_password("DispatchPass123")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def department(db):
    d = Department(name="Test Bo'lim")
    db.session.add(d)
    db.session.commit()
    return d


@pytest.fixture()
def building(db):
    b = Building(name="Test Bino")
    db.session.add(b)
    db.session.commit()
    return b


@pytest.fixture()
def executor_user(db, department, building):
    u = User(full_name="Test Executor", username="test_executor", role=RoleEnum.EXECUTOR,
             telegram_id="111222333")
    u.set_password("ExecPass123")
    u.departments = [department]
    u.buildings = [building]
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def category(db, department):
    c = ServiceCategory(name_uz="Test Kategoriya", department_id=department.id,
                         default_priority=Priority.MEDIUM, default_sla_hours=24, is_active=True)
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture()
def customer(db):
    c = Customer(telegram_id="999888777", full_name="Test Mijoz", phone="998900000000")
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture()
def service_request(db, customer, category, building):
    r = ServiceRequest(
        number="REQ-TEST-000001", customer_id=customer.id, category_id=category.id,
        building_id=building.id, description="Test tavsif", status=RequestStatus.NEW,
        priority=Priority.MEDIUM,
    )
    db.session.add(r)
    db.session.commit()
    return r


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password},
                        follow_redirects=True)
