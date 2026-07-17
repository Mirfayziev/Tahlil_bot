"""AI avtomatik yo'naltirish — bo'lim/bino bo'yicha moslik testlari."""
from datetime import datetime, timedelta

from app.models import ServiceRequest, RequestAssignment, RequestStatus, User, RoleEnum, Department, Building
from app.ai.auto_assign import auto_assign_pending_requests


def _make_stale_request(db, customer, category, building=None):
    r = ServiceRequest(
        number=f"REQ-STALE-{customer.id}", customer_id=customer.id, category_id=category.id,
        building_id=building.id if building else None,
        description="Kechikkan murojaat", status=RequestStatus.NEW,
        created_at=datetime.utcnow() - timedelta(minutes=30),
    )
    db.session.add(r)
    db.session.commit()
    return r


def test_auto_assign_picks_matching_department_executor(app, db, customer, category, executor_user):
    req = _make_stale_request(db, customer, category)
    with app.app_context():
        auto_assign_pending_requests()
    db.session.refresh(req)
    assignment = RequestAssignment.query.filter_by(request_id=req.id).first()
    assert assignment is not None
    assert assignment.executor_id == executor_user.id
    assert req.status == RequestStatus.SENT_TO_EXECUTOR


def test_auto_assign_skips_when_no_department_match(app, db, customer, category):
    """Kategoriya bo'limga bog'langan, lekin hech kim shu bo'limga biriktirilmagan bo'lsa —
    xato odamga yubormasdan, tayinlanmasdan qoladi."""
    req = _make_stale_request(db, customer, category)
    with app.app_context():
        auto_assign_pending_requests()
    db.session.refresh(req)
    assignment = RequestAssignment.query.filter_by(request_id=req.id).first()
    assert assignment is None
    assert req.status == RequestStatus.NEW


def test_auto_assign_respects_building_scoping(app, db, customer, category, executor_user, building):
    """Ijrochi boshqa binoga biriktirilgan bo'lsa, shu bo'limdagi lekin boshqa binodagi
    murojaatga avtomatik tayinlanmasligi kerak."""
    other_building = Building(name="Boshqa bino test")
    db.session.add(other_building)
    db.session.commit()

    second_executor = User(full_name="Ikkinchi ijrochi", username="second_exec_autoassign",
                            role=RoleEnum.EXECUTOR, telegram_id="777888999")
    second_executor.set_password("Pass12345")
    second_executor.departments = executor_user.departments
    second_executor.buildings = [other_building]
    db.session.add(second_executor)
    db.session.commit()

    req = _make_stale_request(db, customer, category, building=other_building)
    with app.app_context():
        auto_assign_pending_requests()
    db.session.refresh(req)
    assignment = RequestAssignment.query.filter_by(request_id=req.id).first()
    assert assignment is not None
    assert assignment.executor_id == second_executor.id
