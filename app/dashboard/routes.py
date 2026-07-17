from datetime import datetime, timedelta
from collections import defaultdict

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func

from app.extensions import db, cache
from app.models import (
    ServiceRequest, RequestStatus, ServiceCategory, User, RoleEnum,
    Department, Rating, RequestAssignment, executor_departments
)
from app.ai.service import generate_manager_insights

dashboard_bp = Blueprint("dashboard", __name__)

# Hali yakunlanmagan (ochiq) murojaatlar holati — summary/sla-status ikkalasida ham kerak.
OPEN_STATUSES = [RequestStatus.NEW, RequestStatus.ACCEPTED, RequestStatus.SENT_TO_EXECUTOR,
                 RequestStatus.IN_PROGRESS, RequestStatus.WAITING_INFO]


@dashboard_bp.route("/")
@login_required
def index():
    return render_template("dashboard/index.html")


@dashboard_bp.route("/ratings")
@login_required
def ratings_list():
    stars_filter = request.args.get("stars", type=int)

    query = Rating.query.join(ServiceRequest, Rating.request_id == ServiceRequest.id)
    if stars_filter:
        query = query.filter(Rating.stars == stars_filter)
    ratings = query.order_by(Rating.created_at.desc()).limit(300).all()

    total = Rating.query.count()
    avg_stars = db.session.query(func.avg(Rating.stars)).scalar() or 0
    distribution = {n: Rating.query.filter_by(stars=n).count() for n in range(5, 0, -1)}
    with_comment = Rating.query.filter(Rating.comment.isnot(None), Rating.comment != "").count()
    with_suggestion = Rating.query.filter(Rating.suggestion.isnot(None), Rating.suggestion != "").count()

    return render_template(
        "dashboard/ratings.html", ratings=ratings, total=total, avg_stars=round(float(avg_stars), 2),
        distribution=distribution, with_comment=with_comment, with_suggestion=with_suggestion,
        stars_filter=stars_filter,
    )


def _period_bounds(period: str):
    now = datetime.utcnow()
    if period == "kunlik":
        return now - timedelta(days=1)
    if period == "haftalik":
        return now - timedelta(weeks=1)
    if period == "choraklik":
        return now - timedelta(days=90)
    if period == "yillik":
        return now - timedelta(days=365)
    return now - timedelta(days=30)  # oylik (default)


@dashboard_bp.route("/api/dashboard/summary")
@login_required
@cache.memoize(timeout=30)
def summary():
    total = ServiceRequest.query.count()
    open_count = ServiceRequest.query.filter(ServiceRequest.status.in_(OPEN_STATUSES)).count()
    done = ServiceRequest.query.filter(ServiceRequest.status == RequestStatus.DONE).count()
    closed = ServiceRequest.query.filter(ServiceRequest.status == RequestStatus.CLOSED).count()
    rejected = ServiceRequest.query.filter(ServiceRequest.status == RequestStatus.REJECTED).count()

    # Har bir ochiq murojaatni yuklab, Python'da is_overdue tekshirish o'rniga
    # to'g'ridan-to'g'ri DB'da hisoblaymiz (katta hajmda ancha tezroq va kam xotira sarflaydi).
    overdue = ServiceRequest.query.filter(
        ServiceRequest.status.in_(OPEN_STATUSES),
        ServiceRequest.deadline_at.isnot(None),
        ServiceRequest.deadline_at < datetime.utcnow(),
    ).count()

    avg_rating = db.session.query(func.avg(Rating.stars)).scalar() or 0

    return jsonify({
        "total": total, "open": open_count, "done": done, "closed": closed,
        "rejected": rejected, "overdue": overdue, "avg_rating": round(float(avg_rating), 2),
        "sla_ok_percent": round(100 * (1 - (overdue / open_count)), 1) if open_count else 100.0,
    })


@dashboard_bp.route("/api/dashboard/dynamics")
@login_required
@cache.cached(timeout=30, query_string=True)
def dynamics():
    period = request.args.get("period", "oylik")
    since = _period_bounds(period)
    rows = db.session.query(
        func.date(ServiceRequest.created_at).label("day"),
        func.count(ServiceRequest.id)
    ).filter(ServiceRequest.created_at >= since).group_by("day").order_by("day").all()

    return jsonify([{"date": str(r[0]), "count": r[1]} for r in rows])


@dashboard_bp.route("/api/dashboard/top-categories")
@login_required
@cache.memoize(timeout=30)
def top_categories():
    rows = db.session.query(
        ServiceCategory.name_uz, func.count(ServiceRequest.id)
    ).join(ServiceRequest, ServiceRequest.category_id == ServiceCategory.id
           ).group_by(ServiceCategory.name_uz).order_by(func.count(ServiceRequest.id).desc()).limit(10).all()
    return jsonify([{"category": r[0], "count": r[1]} for r in rows])


@dashboard_bp.route("/api/dashboard/top-executors")
@login_required
@cache.memoize(timeout=30)
def top_executors():
    rows = db.session.query(
        User.full_name,
        func.count(RequestAssignment.id).label("cnt")
    ).join(RequestAssignment, RequestAssignment.executor_id == User.id
           ).filter(User.role == RoleEnum.EXECUTOR
                    ).group_by(User.full_name).order_by(func.count(RequestAssignment.id).desc()).limit(10).all()
    return jsonify([{"executor": r[0], "count": r[1]} for r in rows])


@dashboard_bp.route("/api/dashboard/sla-status")
@login_required
@cache.memoize(timeout=30)
def sla_status():
    open_count = ServiceRequest.query.filter(ServiceRequest.status.in_(OPEN_STATUSES)).count()
    overdue = ServiceRequest.query.filter(
        ServiceRequest.status.in_(OPEN_STATUSES),
        ServiceRequest.deadline_at.isnot(None),
        ServiceRequest.deadline_at < datetime.utcnow(),
    ).count()
    on_time = open_count - overdue
    return jsonify({"on_time": on_time, "overdue": overdue})


@dashboard_bp.route("/api/dashboard/department-breakdown")
@login_required
@cache.memoize(timeout=30)
def department_breakdown():
    rows = db.session.query(
        Department.name, func.count(RequestAssignment.id)
    ).join(executor_departments, executor_departments.c.department_id == Department.id
           ).join(User, User.id == executor_departments.c.user_id
                  ).join(RequestAssignment, RequestAssignment.executor_id == User.id
                         ).group_by(Department.name).all()
    return jsonify([{"department": r[0], "count": r[1]} for r in rows])


@dashboard_bp.route("/api/dashboard/ai-insights")
@login_required
def ai_insights():
    """AI orqali rahbar uchun xulosalar (TZ p.13)."""
    summary_data = summary().get_json()
    top_cats = top_categories().get_json()
    top_execs = top_executors().get_json()
    sla = sla_status().get_json()

    stats = {"summary": summary_data, "top_categories": top_cats,
             "top_executors": top_execs, "sla": sla}
    insight_text = generate_manager_insights(stats)
    return jsonify({"insights": insight_text or
                    "AI xulosalari uchun ANTHROPIC_API_KEY sozlanishi kerak."})


@dashboard_bp.route("/api/dashboard/ai-auto-assign-status")
@login_required
def ai_auto_assign_status():
    """AI avtomatik yo'naltirish navbatidagi murojaatlar sonini ko'rsatadi (shaffoflik uchun)."""
    from flask import current_app
    after_minutes = current_app.config.get("AUTO_ASSIGN_AFTER_MINUTES", 15)
    threshold = datetime.utcnow() - timedelta(minutes=after_minutes)

    pending_count = ServiceRequest.query.filter(
        ServiceRequest.status == RequestStatus.NEW,
        ServiceRequest.created_at <= threshold,
    ).count()

    waiting_count = ServiceRequest.query.filter(
        ServiceRequest.status == RequestStatus.NEW,
        ServiceRequest.created_at > threshold,
    ).count()

    return jsonify({
        "enabled": current_app.config.get("AUTO_ASSIGN_ENABLED", True),
        "after_minutes": after_minutes,
        "pending_auto_assign": pending_count,
        "waiting_before_auto_assign": waiting_count,
    })
