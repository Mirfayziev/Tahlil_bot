from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import or_

from app.extensions import db
from app.decorators import internal_api_required
from app.models import (
    Customer, ServiceCategory, ServiceRequest, RequestStatus, Priority,
    RequestAttachment, RequestAssignment, RequestStatusLog, Rating,
    User, RoleEnum, Department, Building
)
from app.ai.service import analyze_request_text
from app.notify import notify

api_bp = Blueprint("api", __name__)


def _gen_request_number():
    year = datetime.utcnow().year
    count = ServiceRequest.query.filter(
        ServiceRequest.number.like(f"REQ-{year}-%")
    ).count() + 1
    return f"REQ-{year}-{count:06d}"


# ---------------------------------------------------------------------------
# Mijozlar (Bot №1)
# ---------------------------------------------------------------------------
@api_bp.route("/customers", methods=["POST"])
@internal_api_required
def upsert_customer():
    data = request.get_json(force=True)
    telegram_id = str(data["telegram_id"])
    customer = Customer.query.filter_by(telegram_id=telegram_id).first()
    if not customer:
        customer = Customer(telegram_id=telegram_id)
        db.session.add(customer)

    customer.full_name = data.get("full_name", customer.full_name)
    customer.phone = data.get("phone", customer.phone)
    customer.language = data.get("language", customer.language or "uz")
    db.session.commit()
    return jsonify({"id": customer.id, "telegram_id": customer.telegram_id,
                     "full_name": customer.full_name, "phone": customer.phone})


@api_bp.route("/categories", methods=["GET"])
@internal_api_required
def list_categories():
    lang = request.args.get("lang", "uz")
    cats = ServiceCategory.query.filter_by(is_active=True).order_by(ServiceCategory.sort_order).all()
    return jsonify([
        {"id": c.id, "name": c.display_name(lang), "parent_id": c.parent_id}
        for c in cats
    ])


@api_bp.route("/departments", methods=["GET"])
@internal_api_required
def list_departments():
    """Bot №1 orqali murojatchi tanlashi uchun Departamentlar ro'yxati."""
    deps = Department.query.order_by(Department.name).all()
    return jsonify([{"id": d.id, "name": d.name} for d in deps])


@api_bp.route("/buildings", methods=["GET"])
@internal_api_required
def list_buildings():
    """Bot №1 orqali murojatchi tanlashi uchun Binolar ro'yxati."""
    buildings = Building.query.order_by(Building.name).all()
    return jsonify([{"id": b.id, "name": b.name} for b in buildings])


@api_bp.route("/requests", methods=["POST"])
@internal_api_required
def create_request():
    """Bot №1 orqali yangi murojaat yaratish."""
    data = request.get_json(force=True)

    customer = Customer.query.filter_by(telegram_id=str(data["telegram_id"])).first()
    if not customer:
        return jsonify({"error": "customer not found"}), 404

    category = ServiceCategory.query.get(data["category_id"])
    if not category:
        return jsonify({"error": "category not found"}), 404

    req = ServiceRequest(
        number=_gen_request_number(),
        customer_id=customer.id,
        category_id=category.id,
        building_id=data.get("building_id"),
        description=data.get("description", ""),
        address_text=data.get("address_text"),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        org_department=data.get("org_department"),
        org_division=data.get("org_division"),
        org_is_independent=bool(data.get("org_is_independent", False)),
        room_number=data.get("room_number"),
        priority=category.default_priority or Priority.MEDIUM,
        status=RequestStatus.NEW,
    )
    db.session.add(req)
    db.session.flush()  # req.id ni olish uchun

    for att in data.get("attachments", []):
        db.session.add(RequestAttachment(
            request_id=req.id, file_type=att.get("file_type"), file_ref=att.get("file_ref"),
            stage="murojaat", uploaded_by_type="customer", uploaded_by_id=customer.id
        ))

    db.session.add(RequestStatusLog(
        request_id=req.id, old_status=None, new_status=RequestStatus.NEW.value,
        changed_by_type="customer", changed_by_id=customer.id
    ))

    # AI orqali avtomatik tahlil (kategoriya/ustuvorlik/xulosa taklifi)
    try:
        categories_all = ServiceCategory.query.filter_by(is_active=True).all()
        ai_result = analyze_request_text(req.description, categories_all)
        if ai_result:
            req.ai_summary = ai_result.get("summary")
            req.ai_draft_reply = ai_result.get("draft_reply")
            if ai_result.get("category_id"):
                req.ai_suggested_category_id = ai_result["category_id"]
            if ai_result.get("priority"):
                req.ai_suggested_priority = ai_result["priority"]
    except Exception:  # noqa: BLE001 — AI ishlamasa ham murojaat yaratilishi kerak
        current_app.logger.exception("AI tahlili murojaat yaratishda ishlamadi")

    # Dispatcherlarga zudlik bilan bildirishnoma
    dispatchers = User.query.filter(User.role.in_([RoleEnum.DISPATCHER, RoleEnum.ADMINISTRATOR])).all()
    for d in dispatchers:
        notify("dispatcher", d.id, f"🆕 Yangi murojaat: {req.number} — {category.name_uz}\n{req.org_display}")

    db.session.commit()
    return jsonify({"id": req.id, "number": req.number, "status": req.status.value})


@api_bp.route("/requests/customer/<telegram_id>", methods=["GET"])
@internal_api_required
def list_customer_requests(telegram_id):
    customer = Customer.query.filter_by(telegram_id=str(telegram_id)).first()
    if not customer:
        return jsonify([])
    reqs = ServiceRequest.query.filter_by(customer_id=customer.id).order_by(
        ServiceRequest.created_at.desc()).limit(50).all()
    return jsonify([_serialize_request_short(r) for r in reqs])


@api_bp.route("/requests/<int:req_id>", methods=["GET"])
@internal_api_required
def get_request(req_id):
    req = ServiceRequest.query.get_or_404(req_id)
    return jsonify(_serialize_request_full(req))


@api_bp.route("/requests/<int:req_id>/rate", methods=["POST"])
@internal_api_required
def rate_request(req_id):
    data = request.get_json(force=True)
    req = ServiceRequest.query.get_or_404(req_id)
    if req.rating:
        return jsonify({"error": "already rated"}), 400

    rating = Rating(
        request_id=req.id, stars=int(data["stars"]),
        comment=data.get("comment"), suggestion=data.get("suggestion"),
    )
    db.session.add(rating)
    db.session.commit()
    return jsonify({"ok": True})


def _serialize_request_short(r: ServiceRequest) -> dict:
    executor = r.current_executor
    return {
        "id": r.id, "number": r.number, "category": r.category.name_uz,
        "building": r.building.name if r.building else None,
        "status": r.status.value, "priority": r.priority.value if r.priority else None,
        "created_at": r.created_at.isoformat(),
        "deadline_at": r.deadline_at.isoformat() if r.deadline_at else None,
        "is_overdue": r.is_overdue,
        "executor_name": executor.full_name if executor else None,
        "executor_phone": executor.phone if executor else None,
    }


def _serialize_request_full(r: ServiceRequest) -> dict:
    base = _serialize_request_short(r)
    base.update({
        "description": r.description,
        "address_text": r.address_text,
        "org_department": r.org_department,
        "org_division": r.org_division,
        "org_is_independent": r.org_is_independent,
        "room_number": r.room_number,
        "reject_reason": r.reject_reason,
        "attachments": [
            {"type": a.file_type, "ref": a.file_ref, "stage": a.stage} for a in r.attachments
        ],
        "status_logs": [
            {"old": l.old_status, "new": l.new_status, "comment": l.comment,
             "at": l.created_at.isoformat()} for l in r.status_logs
        ],
    })
    return base


# ---------------------------------------------------------------------------
# Ijrochilar (Bot №2)
# ---------------------------------------------------------------------------
@api_bp.route("/executors/<telegram_id>/tasks", methods=["GET"])
@internal_api_required
def executor_tasks(telegram_id):
    executor = User.query.filter_by(telegram_id=str(telegram_id), role=RoleEnum.EXECUTOR).first()
    if not executor:
        return jsonify({"error": "executor not found"}), 404

    assignments = RequestAssignment.query.filter_by(executor_id=executor.id).filter(
        or_(RequestAssignment.response.is_(None), RequestAssignment.response != "rad_etildi")
    ).order_by(RequestAssignment.assigned_at.desc()).all()

    result = []
    for a in assignments:
        r = a.request
        if r.status in (RequestStatus.DONE, RequestStatus.CLOSED, RequestStatus.REJECTED):
            continue
        result.append({
            "assignment_id": a.id, "request_id": r.id, "number": r.number,
            "category": r.category.name_uz, "building": r.building.name if r.building else None,
            "description": r.description,
            "address": r.address_text, "org_display": r.org_display,
            "priority": r.priority.value if r.priority else None,
            "deadline_at": r.deadline_at.isoformat() if r.deadline_at else None,
            "response": a.response, "status": r.status.value,
            "attachments": [{"type": att.file_type, "ref": att.file_ref} for att in r.attachments
                            if att.stage == "murojaat"],
        })
    return jsonify(result)


@api_bp.route("/assignments/<int:assignment_id>/respond", methods=["POST"])
@internal_api_required
def respond_assignment(assignment_id):
    data = request.get_json(force=True)
    decision = data.get("decision")  # "qabul_qilindi" / "rad_etildi"
    reason = data.get("reason")

    a = RequestAssignment.query.get_or_404(assignment_id)
    a.response = decision
    a.reject_reason = reason
    req = a.request

    old = req.status
    if decision == "qabul_qilindi":
        req.status = RequestStatus.SENT_TO_EXECUTOR
        notify("customer", req.customer_id,
               f"✅ Murojaatingiz ({req.number}) qabul qilindi.\n"
               f"Mas'ul mutaxassis: {a.executor.full_name} ({a.executor.phone or 'tel. ko\u2018rsatilmagan'})")
    else:
        a.executor.workload = max((a.executor.workload or 1) - 1, 0)
        # boshqa faol tayinlov bormi tekshiramiz
        other_active = [x for x in req.assignments if x.id != a.id and x.response != "rad_etildi"]
        if not other_active:
            req.status = RequestStatus.ACCEPTED  # dispatcherga qaytadi, qayta tayinlash kerak
            if req.dispatcher_id:
                notify("dispatcher", req.dispatcher_id,
                       f"⚠️ {req.number} ijrochi tomonidan rad etildi (sabab: {reason or '-'}). "
                       f"Qayta tayinlash kerak.")

    db.session.add(RequestStatusLog(
        request_id=req.id, old_status=old.value, new_status=req.status.value,
        changed_by_type="executor", changed_by_id=a.executor_id, comment=reason
    ))
    db.session.commit()
    return jsonify({"ok": True, "status": req.status.value})


@api_bp.route("/assignments/<int:assignment_id>/start", methods=["POST"])
@internal_api_required
def start_assignment(assignment_id):
    a = RequestAssignment.query.get_or_404(assignment_id)
    a.started_at = datetime.utcnow()
    req = a.request
    old = req.status
    req.status = RequestStatus.IN_PROGRESS
    db.session.add(RequestStatusLog(
        request_id=req.id, old_status=old.value, new_status=req.status.value,
        changed_by_type="executor", changed_by_id=a.executor_id
    ))
    notify("customer", req.customer_id, f"🔧 Murojaatingiz ({req.number}) bo'yicha ish boshlandi (Jarayonda).")
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/assignments/<int:assignment_id>/request-info", methods=["POST"])
@internal_api_required
def request_more_info(assignment_id):
    data = request.get_json(force=True)
    a = RequestAssignment.query.get_or_404(assignment_id)
    req = a.request
    old = req.status
    req.status = RequestStatus.WAITING_INFO
    db.session.add(RequestStatusLog(
        request_id=req.id, old_status=old.value, new_status=req.status.value,
        changed_by_type="executor", changed_by_id=a.executor_id, comment=data.get("question")
    ))
    notify("customer", req.customer_id,
           f"❓ Ijrochi qo'shimcha ma'lumot so'ramoqda ({req.number}): {data.get('question', '')}")
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/assignments/<int:assignment_id>/complete", methods=["POST"])
@internal_api_required
def complete_assignment(assignment_id):
    data = request.get_json(force=True)
    a = RequestAssignment.query.get_or_404(assignment_id)
    a.finished_at = datetime.utcnow()
    a.report_text = data.get("report_text")
    a.time_spent_minutes = data.get("time_spent_minutes")

    for att in data.get("attachments", []):
        db.session.add(RequestAttachment(
            request_id=a.request_id, file_type=att.get("file_type"), file_ref=att.get("file_ref"),
            stage="bajarilgan_ish", uploaded_by_type="executor", uploaded_by_id=a.executor_id
        ))

    req = a.request
    old = req.status
    req.status = RequestStatus.DONE
    req.completed_at = datetime.utcnow()

    a.executor.workload = max((a.executor.workload or 1) - 1, 0)

    db.session.add(RequestStatusLog(
        request_id=req.id, old_status=old.value, new_status=req.status.value,
        changed_by_type="executor", changed_by_id=a.executor_id, comment=a.report_text
    ))
    rating_keyboard = {
        "inline_keyboard": [
            [{"text": "⭐" * n, "callback_data": f"rate:{req.id}:{n}"}] for n in range(5, 0, -1)
        ]
    }
    notify("customer", req.customer_id,
           f"🎉 Murojaatingiz ({req.number}) bajarildi! Iltimos, xizmatni baholang:",
           reply_markup=rating_keyboard)
    if req.dispatcher_id:
        notify("dispatcher", req.dispatcher_id,
               f"✔️ {req.number} ijrochi tomonidan bajarildi deb belgilandi.")
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.route("/assignments/<int:assignment_id>/extend", methods=["POST"])
@internal_api_required
def extend_assignment(assignment_id):
    data = request.get_json(force=True)
    a = RequestAssignment.query.get_or_404(assignment_id)
    a.extra_time_requested = True
    a.extra_time_reason = data.get("reason")

    hours = int(data.get("extra_hours", 4))
    req = a.request
    base = req.deadline_at or datetime.utcnow()
    a.new_deadline = base + timedelta(hours=hours)

    if req.dispatcher_id:
        notify("dispatcher", req.dispatcher_id,
               f"⏱ {req.number} uchun ijrochi qo'shimcha vaqt so'ramoqda "
               f"({hours} soat). Sabab: {data.get('reason', '-')}")
    db.session.commit()
    return jsonify({"ok": True, "new_deadline": a.new_deadline.isoformat()})


@api_bp.route("/assignments/<int:assignment_id>/approve-extension", methods=["POST"])
@internal_api_required
def approve_extension(assignment_id):
    a = RequestAssignment.query.get_or_404(assignment_id)
    if a.new_deadline:
        a.request.deadline_at = a.new_deadline
        db.session.commit()
    return jsonify({"ok": True})
