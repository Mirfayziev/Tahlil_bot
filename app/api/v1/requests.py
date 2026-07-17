"""Versiyalangan ochiq API — murojaatlar va topshiriqlar (TZ v2, bo'lim 2: API).

Bu JWT bilan himoyalangan, tashqi mijozlar (masalan Mobil ilova, TZ bo'lim 8) uchun
mo'ljallangan API. Botlar hamon ichki X-Internal-Token orqali /api/... dan foydalanadi.
"""
from datetime import datetime

from flask import jsonify, g, request

from app.api.v1 import api_v1_bp
from app.api.v1.jwt_utils import jwt_required
from app.api.v1.schemas import CompleteAssignmentSchema, RespondAssignmentSchema
from app.extensions import db
from app.models import ServiceRequest, RequestAssignment, RequestStatus, RequestStatusLog, RoleEnum
from app.notify import notify


def _serialize_request(r: ServiceRequest) -> dict:
    return {
        "id": r.id, "number": r.number, "category": r.category.name_uz if r.category else None,
        "building": r.building.name if r.building else None,
        "status": r.status.value, "priority": r.priority.value if r.priority else None,
        "description": r.description, "org_display": r.org_display,
        "created_at": r.created_at.isoformat(),
        "deadline_at": r.deadline_at.isoformat() if r.deadline_at else None,
        "is_overdue": r.is_overdue,
    }


@api_v1_bp.route("/requests", methods=["GET"])
@jwt_required
def v1_list_requests():
    """
    Murojaatlar ro'yxati (rolga qarab cheklangan, sahifalangan)
    ---
    tags: [Requests]
    security: [{BearerAuth: []}]
    parameters:
      - in: query
        name: page
        type: integer
      - in: query
        name: per_page
        type: integer
    responses:
      200:
        description: sahifalangan murojaatlar ro'yxati
    """
    user = g.current_user
    query = ServiceRequest.query

    if user.role == RoleEnum.EXECUTOR:
        assigned_ids = [a.request_id for a in RequestAssignment.query.filter_by(executor_id=user.id).all()]
        query = query.filter(ServiceRequest.id.in_(assigned_ids)) if assigned_ids else query.filter(ServiceRequest.id == -1)

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    pagination = query.order_by(ServiceRequest.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "page": page, "per_page": per_page, "total": pagination.total, "pages": pagination.pages,
        "items": [_serialize_request(r) for r in pagination.items],
    })


@api_v1_bp.route("/requests/<int:req_id>", methods=["GET"])
@jwt_required
def v1_get_request(req_id):
    """
    Murojaat tafsiloti
    ---
    tags: [Requests]
    security: [{BearerAuth: []}]
    parameters:
      - in: path
        name: req_id
        type: integer
        required: true
    responses:
      200:
        description: murojaat tafsiloti
      404:
        description: topilmadi
    """
    req = ServiceRequest.query.get_or_404(req_id)
    return jsonify(_serialize_request(req))


@api_v1_bp.route("/my-tasks", methods=["GET"])
@jwt_required
def v1_my_tasks():
    """
    Ijrochining o'z topshiriqlari (faqat 'ijrochi' rolidagilar uchun)
    ---
    tags: [Requests]
    security: [{BearerAuth: []}]
    responses:
      200:
        description: joriy foydalanuvchiga tayinlangan topshiriqlar
      403:
        description: bu endpoint faqat ijrochilar uchun
    """
    user = g.current_user
    if user.role != RoleEnum.EXECUTOR:
        return jsonify({"error": "bu endpoint faqat ijrochilar uchun"}), 403

    assignments = RequestAssignment.query.filter_by(executor_id=user.id).order_by(
        RequestAssignment.assigned_at.desc()
    ).all()
    return jsonify([{
        "assignment_id": a.id, "response": a.response,
        "request": _serialize_request(a.request),
    } for a in assignments])


@api_v1_bp.route("/assignments/<int:assignment_id>/respond", methods=["POST"])
@jwt_required
def v1_respond_assignment(assignment_id):
    """
    Topshiriqni qabul qilish yoki rad etish
    ---
    tags: [Assignments]
    security: [{BearerAuth: []}]
    responses:
      200: {description: holat yangilandi}
      403: {description: bu topshiriq sizga tegishli emas}
      422: {description: validatsiya xatosi}
    """
    user = g.current_user
    a = RequestAssignment.query.get_or_404(assignment_id)
    if a.executor_id != user.id:
        return jsonify({"error": "bu topshiriq sizga tegishli emas"}), 403

    data = request.get_json(silent=True) or {}
    errors = RespondAssignmentSchema().validate(data)
    if errors:
        return jsonify({"errors": errors}), 422

    a.response = data["decision"]
    a.reject_reason = data.get("reason")
    req = a.request
    old = req.status

    if data["decision"] == "qabul_qilindi":
        req.status = RequestStatus.SENT_TO_EXECUTOR
        notify("customer", req.customer_id,
               f"✅ Murojaatingiz ({req.number}) qabul qilindi.\n"
               f"Mas'ul mutaxassis: {user.full_name} ({user.phone or 'tel. ko‘rsatilmagan'})")
    else:
        user.workload = max((user.workload or 1) - 1, 0)
        other_active = [x for x in req.assignments if x.id != a.id and x.response != "rad_etildi"]
        if not other_active:
            req.status = RequestStatus.ACCEPTED
            if req.dispatcher_id:
                notify("dispatcher", req.dispatcher_id,
                       f"⚠️ {req.number} ijrochi tomonidan rad etildi (sabab: {data.get('reason') or '-'}).")

    db.session.add(RequestStatusLog(
        request_id=req.id, old_status=old.value, new_status=req.status.value,
        changed_by_type="executor", changed_by_id=user.id, comment=data.get("reason")
    ))
    db.session.commit()
    return jsonify({"ok": True, "status": req.status.value})


@api_v1_bp.route("/assignments/<int:assignment_id>/complete", methods=["POST"])
@jwt_required
def v1_complete_assignment(assignment_id):
    """
    Topshiriqni bajarildi deb belgilash
    ---
    tags: [Assignments]
    security: [{BearerAuth: []}]
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [report_text]
          properties:
            report_text: {type: string}
            time_spent_minutes: {type: integer}
    responses:
      200: {description: bajarildi deb belgilandi}
      403: {description: bu topshiriq sizga tegishli emas}
      422: {description: validatsiya xatosi}
    """
    user = g.current_user
    a = RequestAssignment.query.get_or_404(assignment_id)
    if a.executor_id != user.id:
        return jsonify({"error": "bu topshiriq sizga tegishli emas"}), 403

    data = request.get_json(silent=True) or {}
    errors = CompleteAssignmentSchema().validate(data)
    if errors:
        return jsonify({"errors": errors}), 422

    a.finished_at = datetime.utcnow()
    a.report_text = data["report_text"]
    a.time_spent_minutes = data.get("time_spent_minutes")

    req = a.request
    old = req.status
    req.status = RequestStatus.DONE
    req.completed_at = datetime.utcnow()
    user.workload = max((user.workload or 1) - 1, 0)

    db.session.add(RequestStatusLog(
        request_id=req.id, old_status=old.value, new_status=req.status.value,
        changed_by_type="executor", changed_by_id=user.id, comment=a.report_text
    ))

    rating_keyboard = {
        "inline_keyboard": [[{"text": "⭐" * n, "callback_data": f"rate:{req.id}:{n}"}] for n in range(5, 0, -1)]
    }
    notify("customer", req.customer_id,
           f"🎉 Murojaatingiz ({req.number}) bajarildi! Iltimos, xizmatni baholang:",
           reply_markup=rating_keyboard)
    if req.dispatcher_id:
        notify("dispatcher", req.dispatcher_id, f"✔️ {req.number} ijrochi tomonidan bajarildi deb belgilandi.")

    db.session.commit()
    return jsonify({"ok": True})
