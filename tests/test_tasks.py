"""Celery vazifalari (app/tasks.py) — Redis/broker'siz, to'g'ridan-to'g'ri chaqirib tekshiriladi."""
from datetime import datetime, timedelta

from app.models import ServiceRequest, RequestAssignment, Notification
from app.tasks import (
    scan_deadlines_task, run_auto_assign_task, process_pending_notifications_task,
    generate_scheduled_report_task,
)


def test_scan_deadlines_task_creates_warning(app, db, customer, category, executor_user):
    req = ServiceRequest(
        number="REQ-DEADLINE-001", customer_id=customer.id, category_id=category.id,
        description="Muddat testi", deadline_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db.session.add(req)
    db.session.flush()
    db.session.add(RequestAssignment(request_id=req.id, executor_id=executor_user.id))
    db.session.commit()

    result = scan_deadlines_task()
    assert result["notifications_created"] >= 1
    assert Notification.query.filter_by(recipient_type="executor", recipient_id=executor_user.id).count() >= 1


def test_run_auto_assign_task_returns_ok(app, db):
    result = run_auto_assign_task()
    assert result == {"ok": True}


def test_process_pending_notifications_task_no_pending(app, db):
    result = process_pending_notifications_task()
    assert result["processed"] == 0


def test_process_pending_notifications_task_processes_queue(app, db, customer):
    from app.notify import notify
    notify("customer", customer.id, "Test xabar")
    db.session.commit()

    result = process_pending_notifications_task()
    assert result["processed"] == 1


def test_generate_scheduled_report_task_computes_stats(app, db, service_request):
    result = generate_scheduled_report_task()
    assert "new_count" in result
    assert result["new_count"] >= 1
    assert result["email_sent"] is False  # MAIL_SERVER sozlanmagan test muhitida
