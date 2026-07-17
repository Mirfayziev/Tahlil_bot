"""
AI avtomatik yo'naltirish (TZ p.13): agar dispetcher belgilangan vaqt ichida
murojaatni qabul qilib, ijrochiga yubormasa, AI o'zi murojaat kategoriyasi
(yoki AI taklif qilgan kategoriya) asosida tegishli bo'limdagi eng bo'sh
ijrochiga avtomatik tayinlaydi.

Bu modul faqat Flask app_context ichida chaqiriladi (masalan bots/notifier.py dan).
"""
import logging
from datetime import datetime, timedelta

from flask import current_app

logger = logging.getLogger(__name__)


def auto_assign_pending_requests():
    from app.extensions import db
    from app.models import ServiceRequest, RequestStatus, RequestAssignment, RequestStatusLog, User, RoleEnum
    from app.notify import notify

    if not current_app.config.get("AUTO_ASSIGN_ENABLED", True):
        return

    after_minutes = current_app.config.get("AUTO_ASSIGN_AFTER_MINUTES", 15)
    threshold = datetime.utcnow() - timedelta(minutes=after_minutes)

    pending = ServiceRequest.query.filter(
        ServiceRequest.status == RequestStatus.NEW,
        ServiceRequest.created_at <= threshold,
    ).all()

    for req in pending:
        try:
            _auto_assign_one(req, db, RequestAssignment, RequestStatusLog, User, RoleEnum, notify)
        except Exception:
            logger.exception("AI avtomatik yo'naltirishda xatolik: %s", req.number)

    db.session.commit()


def _auto_assign_one(req, db, RequestAssignment, RequestStatusLog, User, RoleEnum, notify):
    from app.models import Department

    # AI taklif qilgan kategoriya bo'lsa, o'shani ustuvor olamiz; bo'lmasa asl kategoriya.
    target_category = req.ai_suggested_category_id and \
        _get_category(req.ai_suggested_category_id) or req.category

    department_id = target_category.department_id if target_category else None
    building_id = req.building_id

    executor_query = User.query.filter_by(role=RoleEnum.EXECUTOR, is_active_flag=True)
    if department_id:
        executor_query = executor_query.filter(User.departments.any(Department.id == department_id))
    candidates = executor_query.order_by(User.workload).all()

    # Kategoriya biror bo'limga bog'lanmagan bo'lsagina (noaniq yo'nalish), eng bo'sh
    # ijrochini olamiz. Agar bo'lim aniq bo'lsa-yu, unga biriktirilgan ijrochi topilmasa,
    # boshqa yo'nalishdagi odamga noto'g'ri yuborilmasligi uchun dispetcherga qoldiramiz.
    if not candidates and not department_id:
        candidates = User.query.filter_by(role=RoleEnum.EXECUTOR, is_active_flag=True).order_by(User.workload).all()

    if building_id:
        building_matches = [u for u in candidates if building_id in [b.id for b in u.buildings]]
        if building_matches:
            candidates = building_matches
        # aks holda hech kim shu binoga biriktirilmagan — bino bo'yicha cheklov qo'llanilmaydi

    executor = candidates[0] if candidates else None

    if not executor:
        logger.warning("AI avtomatik yo'naltirish uchun mos ijrochi topilmadi: %s", req.number)
        return

    db.session.add(RequestAssignment(request_id=req.id, executor_id=executor.id))
    executor.workload = (executor.workload or 0) + 1

    if req.ai_suggested_priority:
        req.priority = req.ai_suggested_priority

    old_status = req.status
    req.status = req.status.__class__.SENT_TO_EXECUTOR
    req.sent_at = datetime.utcnow()

    db.session.add(RequestStatusLog(
        request_id=req.id, old_status=old_status.value, new_status=req.status.value,
        changed_by_type="ai", changed_by_id=None,
        comment=f"AI avtomatik ravishda {executor.full_name} ga yo'naltirdi "
                f"(kategoriya: {target_category.name_uz if target_category else '-'})."
    ))

    notify("executor", executor.id,
           f"🤖 AI orqali avtomatik topshiriq: {req.number} — {target_category.name_uz if target_category else req.category.name_uz}")
    notify("customer", req.customer_id,
           f"📤 Murojaatingiz ({req.number}) mutaxassisga yo'naltirildi:\n"
           f"{executor.full_name} ({executor.phone or 'tel. ko\u2018rsatilmagan'})")


def _get_category(category_id):
    from app.models import ServiceCategory
    return ServiceCategory.query.get(category_id)
