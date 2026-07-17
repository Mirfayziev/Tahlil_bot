"""Celery fon vazifalari — bildirishnoma, muddat nazorati, AI avtomatik yo'naltirish
va rejalashtirilgan hisobotlar (TZ v2, bo'lim 3: DevOps va bo'lim 7: Hisobotlar).

Bular bots/notifier.py dagi mantiqning Celery-asosidagi, production uchun mo'ljallangan
versiyasi — Redis broker orqali Celery Beat jadvali bilan ishga tushadi.
"""
import logging
from datetime import datetime, timedelta

from app.celery_app import celery_app
from app.extensions import db
from app.models import Notification, Customer, User, RequestStatus, ServiceRequest, RoleEnum
from app.notify import send_telegram_message

logger = logging.getLogger("celery.tasks")

DEADLINE_WARNING_MINUTES_BEFORE = 60


def _dispatch_notification(notif: Notification, config) -> bool:
    if notif.recipient_type == "customer":
        customer = Customer.query.get(notif.recipient_id)
        if not customer:
            return False
        return send_telegram_message(config.get("CUSTOMER_BOT_TOKEN"), customer.telegram_id, notif.message)

    if notif.recipient_type == "executor":
        user = User.query.get(notif.recipient_id)
        if not user or not user.telegram_id:
            return False
        return send_telegram_message(config.get("EXECUTOR_BOT_TOKEN"), user.telegram_id, notif.message)

    if notif.recipient_type == "dispatcher":
        user = User.query.get(notif.recipient_id)
        if not user or not user.telegram_id:
            return False
        token = config.get("NOTIFY_BOT_TOKEN") or config.get("EXECUTOR_BOT_TOKEN")
        return send_telegram_message(token, user.telegram_id, notif.message)

    return False


@celery_app.task(name="app.tasks.process_pending_notifications_task")
def process_pending_notifications_task():
    from flask import current_app

    pending = Notification.query.filter_by(is_sent=False).limit(100).all()
    for notif in pending:
        try:
            ok = _dispatch_notification(notif, current_app.config)
            if ok:
                notif.is_sent = True
                notif.sent_at = datetime.utcnow()
        except Exception:
            logger.exception("Bildirishnoma yuborishda xatolik: %s", notif.id)
    db.session.commit()
    return {"processed": len(pending)}


@celery_app.task(name="app.tasks.scan_deadlines_task")
def scan_deadlines_task():
    """Muddati yaqinlashayotgan yoki o'tib ketgan murojaatlar uchun ogohlantirish yaratadi."""
    open_statuses = [RequestStatus.NEW, RequestStatus.ACCEPTED, RequestStatus.SENT_TO_EXECUTOR,
                      RequestStatus.IN_PROGRESS, RequestStatus.WAITING_INFO]
    open_reqs = ServiceRequest.query.filter(ServiceRequest.status.in_(open_statuses)).all()
    now = datetime.utcnow()
    created = 0

    for r in open_reqs:
        if not r.deadline_at:
            continue
        executor = r.current_executor
        if not executor:
            continue

        already_warned = any(
            "muddat tugashiga" in (n.message or "") and n.recipient_id == executor.id
            for n in Notification.query.filter_by(recipient_type="executor", recipient_id=executor.id).all()
        )
        if (r.deadline_at - now) <= timedelta(minutes=DEADLINE_WARNING_MINUTES_BEFORE) and \
                r.deadline_at > now and not already_warned:
            db.session.add(Notification(
                recipient_type="executor", recipient_id=executor.id,
                message=f"⏰ Diqqat! {r.number} bo'yicha muddat tugashiga "
                        f"{DEADLINE_WARNING_MINUTES_BEFORE} daqiqa qoldi."
            ))
            created += 1

        if r.deadline_at < now:
            already_overdue_notified = any(
                "muddati o'tib ketdi" in (n.message or "") and n.recipient_id == executor.id
                for n in Notification.query.filter_by(recipient_type="executor", recipient_id=executor.id).all()
            )
            if not already_overdue_notified:
                db.session.add(Notification(
                    recipient_type="executor", recipient_id=executor.id,
                    message=f"🔴 {r.number} bo'yicha muddati o'tib ketdi! Iltimos, tezroq bajaring."
                ))
                dispatchers = User.query.filter(
                    User.role.in_([RoleEnum.DISPATCHER, RoleEnum.ADMINISTRATOR])
                ).all()
                for d in dispatchers:
                    db.session.add(Notification(
                        recipient_type="dispatcher", recipient_id=d.id,
                        message=f"🔴 {r.number} muddati o'tib ketdi (ijrochi: {executor.full_name})."
                    ))
                created += 1

    db.session.commit()
    return {"notifications_created": created}


@celery_app.task(name="app.tasks.run_auto_assign_task")
def run_auto_assign_task():
    """Dispetcher belgilangan vaqt ichida murojaatga javob bermasa, AI o'zi yo'naltiradi."""
    from app.ai.auto_assign import auto_assign_pending_requests
    auto_assign_pending_requests()
    return {"ok": True}


@celery_app.task(name="app.tasks.generate_scheduled_report_task")
def generate_scheduled_report_task():
    """Har kuni ertalab umumiy hisobotni tayyorlab, super_admin'larga email qiladi
    (TZ v2, bo'lim 7: Hisobotlar — rejalashtirilgan hisobotlar + email yuborish)."""
    from app.reports.scheduled import generate_and_email_daily_report
    return generate_and_email_daily_report()
