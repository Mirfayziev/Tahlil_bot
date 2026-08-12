from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db
from app.decorators import roles_required
from app.models import (
    ServiceRequest, ServiceCategory, User, RequestStatus, Priority,
    RequestAssignment, RequestStatusLog, RoleEnum, Department, Building
)
from app.ai.service import analyze_request_text
from app.notify import notify as _notify

dispatcher_bp = Blueprint("dispatcher", __name__)


def _eligible_executors(req):
    """
    Murojaat kategoriyasi bog'langan Bo'lim va murojaatchi tanlagan Bino bo'yicha mos
    ijrochilarni topadi. Ikkalasi ham mavjud bo'lsa ikkalasi ham (VA) hisobga olinadi;
    agar biror mezon bo'yicha hech kim topilmasa (masalan hali hech kim shu binoga
    biriktirilmagan bo'lsa), shu mezon e'tiborga olinmaydi va dispetcherga ogohlantirish
    ko'rsatiladi — aks holda tayinlash butunlay bloklanib qolar edi.
    """
    department_id = req.category.department_id if req.category else None
    building_id = req.building_id

    query = User.query.filter_by(role=RoleEnum.EXECUTOR, is_active_flag=True).options(
        selectinload(User.buildings)
    )
    if department_id:
        query = query.filter(User.departments.any(Department.id == department_id))
    candidates = query.order_by(User.workload).all()

    unscoped_department = not department_id

    unscoped_building = not building_id
    if building_id:
        building_matches = [u for u in candidates if building_id in [b.id for b in u.buildings]]
        if building_matches:
            candidates = building_matches
        else:
            unscoped_building = True

    return candidates, unscoped_department, unscoped_building


def _log_status(req, old_status, new_status, comment=None):
    db.session.add(RequestStatusLog(
        request_id=req.id, old_status=old_status, new_status=new_status,
        changed_by_type="dispatcher", changed_by_id=current_user.id, comment=comment
    ))


@dispatcher_bp.route("/")
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR, RoleEnum.DISPATCHER, RoleEnum.DEPARTMENT_HEAD)
def requests_list():
    status_filter = request.args.get("status")
    category_filter = request.args.get("category", type=int)
    priority_filter = request.args.get("priority")
    search = request.args.get("q", "").strip()

    query = ServiceRequest.query.options(
        joinedload(ServiceRequest.customer),
        joinedload(ServiceRequest.building),
        joinedload(ServiceRequest.category),
    )

    if status_filter:
        query = query.filter(ServiceRequest.status == status_filter)
    if category_filter:
        query = query.filter(ServiceRequest.category_id == category_filter)
    if priority_filter:
        query = query.filter(ServiceRequest.priority == priority_filter)
    if search:
        query = query.filter(
            (ServiceRequest.number.ilike(f"%{search}%")) |
            (ServiceRequest.description.ilike(f"%{search}%"))
        )

    requests_qs = query.order_by(ServiceRequest.created_at.desc()).limit(200).all()
    categories = ServiceCategory.query.filter_by(is_active=True).all()
    statuses = list(RequestStatus)
    priorities = list(Priority)

    return render_template(
        "dispatcher/requests_list.html",
        requests=requests_qs, categories=categories, statuses=statuses,
        priorities=priorities, current_filters=request.args
    )


@dispatcher_bp.route("/api/new-requests")
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR, RoleEnum.DISPATCHER, RoleEnum.DEPARTMENT_HEAD)
def new_requests_feed():
    """Bell ikonkasi uchun: berilgan ID'dan keyingi yangi murojaatlarni qaytaradi."""
    since_id = request.args.get("since_id", 0, type=int)

    query = ServiceRequest.query.options(joinedload(ServiceRequest.category)).filter(
        ServiceRequest.id > since_id
    )
    if current_user.role == RoleEnum.DEPARTMENT_HEAD and current_user.department_id:
        query = query.join(ServiceCategory).filter(
            ServiceCategory.department_id == current_user.department_id
        )
    items = query.order_by(ServiceRequest.created_at.desc()).limit(30).all()

    latest_id = db.session.query(db.func.max(ServiceRequest.id)).scalar() or 0

    return jsonify({
        "latest_id": latest_id,
        "items": [{
            "id": r.id,
            "number": r.number,
            "category": r.category.name_uz,
            "priority": r.priority.value if r.priority else None,
            "org_display": r.org_display,
            "description": (r.description or "")[:120],
            "created_at": r.created_at.isoformat(),
        } for r in items],
    })


@dispatcher_bp.route("/requests/<int:req_id>")
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR, RoleEnum.DISPATCHER, RoleEnum.DEPARTMENT_HEAD)
def request_detail(req_id):
    req = ServiceRequest.query.options(
        joinedload(ServiceRequest.customer),
        joinedload(ServiceRequest.category),
        joinedload(ServiceRequest.building),
        selectinload(ServiceRequest.attachments),
        selectinload(ServiceRequest.status_logs),
    ).filter(ServiceRequest.id == req_id).first_or_404()
    executors, unscoped_department, unscoped_building = _eligible_executors(req)
    return render_template("dispatcher/request_detail.html", req=req, executors=executors,
                            unscoped_fallback=unscoped_department, unscoped_building=unscoped_building)


@dispatcher_bp.route("/requests/<int:req_id>/accept", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR, RoleEnum.DISPATCHER)
def accept_request(req_id):
    req = ServiceRequest.query.get_or_404(req_id)
    old = req.status
    req.status = RequestStatus.ACCEPTED
    req.accepted_at = datetime.utcnow()
    req.dispatcher_id = current_user.id
    if not req.deadline_at:
        sla = current_app.config["SLA_HOURS"].get(req.priority.value if req.priority else "orta", 24)
        req.deadline_at = datetime.utcnow() + timedelta(hours=sla)
    _log_status(req, old, req.status)
    db.session.commit()
    flash(f"{req.number} qabul qilindi.", "success")
    return redirect(url_for("dispatcher.request_detail", req_id=req.id))


@dispatcher_bp.route("/requests/<int:req_id>/assign", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR, RoleEnum.DISPATCHER)
def assign_request(req_id):
    req = ServiceRequest.query.get_or_404(req_id)
    executor_ids = request.form.getlist("executor_ids")
    deadline_str = request.form.get("deadline")

    if not executor_ids:
        flash("Ijrochi tanlanmadi.", "danger")
        return redirect(url_for("dispatcher.request_detail", req_id=req.id))

    eligible, _, _ = _eligible_executors(req)
    eligible_by_id = {u.id: u for u in eligible}
    for eid in executor_ids:
        if int(eid) not in eligible_by_id:
            executor = User.query.get(int(eid))
            flash(
                f"{executor.full_name if executor else eid} ushbu murojaat "
                f"(kategoriya/bino) yo'nalishiga biriktirilmagan — tayinlash bekor qilindi.",
                "danger",
            )
            return redirect(url_for("dispatcher.request_detail", req_id=req.id))

    photo_att = next((a for a in req.attachments if a.stage == "murojaat" and a.file_type == "photo"), None)
    for eid in executor_ids:
        executor = eligible_by_id[int(eid)]
        db.session.add(RequestAssignment(request_id=req.id, executor_id=executor.id))
        executor.workload = (executor.workload or 0) + 1
        _notify("executor", executor.id, f"Sizga yangi topshiriq keldi: {req.number} — {req.category.name_uz}",
                photo_file_id=photo_att.file_ref if photo_att else None)

    if deadline_str:
        req.deadline_at = datetime.strptime(deadline_str, "%Y-%m-%dT%H:%M")

    old = req.status
    req.status = RequestStatus.SENT_TO_EXECUTOR
    req.sent_at = datetime.utcnow()
    _log_status(req, old, req.status, comment=f"Ijrochilarga yuborildi: {executor_ids}")
    # Mijozga hali ANIQ kim mas'ul ekani aytilmaydi — buni faqat ijrochi qabul qilganda
    # (respond_assignment) bitta, to'g'ri ismi bilan bildiramiz. Aks holda bir nechta
    # nomzod tanlanganda ularning barcha ismi/telefoni mijozga oshkor bo'lib qolar edi.
    _notify("customer", req.customer_id,
            f"📤 Murojaatingiz ({req.number}) mas'ul mutaxassisga yuborildi. Tez orada bog'lanishadi.")
    db.session.commit()
    flash(f"{req.number} ijrochi(lar)ga yuborildi.", "success")
    return redirect(url_for("dispatcher.request_detail", req_id=req.id))


@dispatcher_bp.route("/requests/<int:req_id>/reject", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR, RoleEnum.DISPATCHER)
def reject_request(req_id):
    req = ServiceRequest.query.get_or_404(req_id)
    reason = request.form.get("reason", "")
    old = req.status
    req.status = RequestStatus.REJECTED
    req.reject_reason = reason
    req.closed_at = datetime.utcnow()
    _log_status(req, old, req.status, comment=reason)
    _notify("customer", req.customer_id, f"Murojaatingiz ({req.number}) rad etildi. Sabab: {reason}")
    db.session.commit()
    flash(f"{req.number} rad etildi.", "warning")
    return redirect(url_for("dispatcher.requests_list"))


@dispatcher_bp.route("/requests/<int:req_id>/close", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR, RoleEnum.DISPATCHER)
def close_request(req_id):
    req = ServiceRequest.query.get_or_404(req_id)
    old = req.status
    req.status = RequestStatus.CLOSED
    req.closed_at = datetime.utcnow()
    _log_status(req, old, req.status)
    _notify("customer", req.customer_id,
            f"Murojaatingiz ({req.number}) yopildi. Xizmatni baholashingizni so'raymiz.")
    db.session.commit()
    flash(f"{req.number} yopildi.", "success")
    return redirect(url_for("dispatcher.requests_list"))


@dispatcher_bp.route("/requests/<int:req_id>/reopen", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR, RoleEnum.DISPATCHER)
def reopen_request(req_id):
    """Buyurtmachi bajarilgan ishga e'tiroz bildirsa, dispetcher murojaatni
    qayta jarayonga (ijrochiga) qaytaradi (TZ: sifat nazorati)."""
    req = ServiceRequest.query.get_or_404(req_id)
    reason = request.form.get("reason", "").strip()

    if req.status not in (RequestStatus.DONE, RequestStatus.CLOSED):
        flash("Faqat bajarilgan yoki yopilgan murojaatni qayta jarayonga qaytarish mumkin.", "danger")
        return redirect(url_for("dispatcher.request_detail", req_id=req.id))
    if not reason:
        flash("Qayta jarayonga qaytarish sababini kiriting.", "danger")
        return redirect(url_for("dispatcher.request_detail", req_id=req.id))

    old = req.status
    req.status = RequestStatus.IN_PROGRESS
    req.completed_at = None
    req.closed_at = None

    executor = req.current_executor
    if executor:
        assignment = next(
            (a for a in req.assignments if a.executor_id == executor.id and a.response != "rad_etildi"),
            None,
        )
        if assignment:
            assignment.finished_at = None
        _notify("executor", executor.id,
                f"⚠️ {req.number} buyurtmachi e'tirozi sababli qayta ko'rib chiqishga qaytarildi.\n"
                f"Sabab: {reason}")

    _log_status(req, old, req.status, comment=f"Qayta jarayonga qaytarildi (e'tiroz): {reason}")
    _notify("customer", req.customer_id,
            f"Murojaatingiz ({req.number}) qayta ko'rib chiqilmoqda. Tez orada bog'lanishadi.")
    db.session.commit()
    flash(f"{req.number} qayta jarayonga qaytarildi.", "success")
    return redirect(url_for("dispatcher.request_detail", req_id=req.id))


@dispatcher_bp.route("/requests/<int:req_id>/comment", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR, RoleEnum.DISPATCHER)
def add_comment(req_id):
    req = ServiceRequest.query.get_or_404(req_id)
    comment = request.form.get("comment", "")
    _log_status(req, req.status, req.status, comment=comment)
    db.session.commit()
    flash("Izoh qo'shildi.", "success")
    return redirect(url_for("dispatcher.request_detail", req_id=req.id))


@dispatcher_bp.route("/requests/<int:req_id>/reanalyze-ai", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR, RoleEnum.DISPATCHER)
def reanalyze_ai(req_id):
    req = ServiceRequest.query.get_or_404(req_id)
    categories = ServiceCategory.query.filter_by(is_active=True).all()
    result = analyze_request_text(req.description, categories)
    if result:
        req.ai_summary = result.get("summary")
        req.ai_draft_reply = result.get("draft_reply")
        if result.get("category_id"):
            req.ai_suggested_category_id = result["category_id"]
        if result.get("priority"):
            req.ai_suggested_priority = result["priority"]
        db.session.commit()
        flash("AI tahlili yangilandi.", "success")
    else:
        flash("AI tahlili amalga oshmadi (API kaliti sozlanmagan bo'lishi mumkin).", "warning")
    return redirect(url_for("dispatcher.request_detail", req_id=req.id))


@dispatcher_bp.route("/assignments/<int:assignment_id>/approve-extension", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR, RoleEnum.DISPATCHER)
def approve_extension(assignment_id):
    """Ijrochi botdan yuborgan qo'shimcha vaqt so'rovini tasdiqlaydi (TZ p.15)."""
    assignment = RequestAssignment.query.get_or_404(assignment_id)
    req = assignment.request
    if assignment.new_deadline:
        old = req.status
        req.deadline_at = assignment.new_deadline
        assignment.extra_time_requested = False
        _log_status(req, old, req.status,
                    comment=f"Qo'shimcha vaqt tasdiqlandi: {assignment.new_deadline.strftime('%d.%m.%Y %H:%M')}")
        _notify("executor", assignment.executor_id,
                f"✅ {req.number} uchun qo'shimcha vaqt so'rovingiz tasdiqlandi. "
                f"Yangi muddat: {assignment.new_deadline.strftime('%d.%m.%Y %H:%M')}")
        db.session.commit()
        flash(f"{req.number} — muddat uzaytirildi.", "success")
    else:
        flash("Bu ijrochida hali qo'shimcha vaqt so'rovi yo'q.", "warning")
    return redirect(url_for("dispatcher.request_detail", req_id=req.id))
