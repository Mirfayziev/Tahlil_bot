import secrets
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.decorators import roles_required
from app.security import validate_password_strength
from app.models import (
    ServiceCategory, User, Department, RoleEnum, AuditLog, Building
)

admin_bp = Blueprint("admin", __name__)


def log_action(action, entity, entity_id=None, details=None):
    db.session.add(AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action, entity=entity, entity_id=entity_id, details=details
    ))


# ---------------------------------------------------------------------------
# Xizmat kategoriyalari
# ---------------------------------------------------------------------------
@admin_bp.route("/categories", methods=["GET", "POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR)
def categories():
    if request.method == "POST":
        cat = ServiceCategory(
            name_uz=request.form["name_uz"],
            name_ru=request.form.get("name_ru"),
            name_en=request.form.get("name_en"),
            description=request.form.get("description"),
            parent_id=request.form.get("parent_id") or None,
            department_id=request.form.get("department_id") or None,
            default_priority=request.form.get("default_priority", "orta"),
            default_sla_hours=int(request.form.get("default_sla_hours", 24)),
        )
        db.session.add(cat)
        log_action("create", "ServiceCategory", details=cat.name_uz)
        db.session.commit()
        flash("Kategoriya qo'shildi.", "success")
        return redirect(url_for("admin.categories"))

    all_categories = ServiceCategory.query.order_by(ServiceCategory.sort_order).all()
    top_level = [c for c in all_categories if c.parent_id is None]
    departments = Department.query.all()
    return render_template("admin/categories.html", categories=all_categories, top_level=top_level,
                            departments=departments)


@admin_bp.route("/categories/<int:cat_id>/toggle", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR)
def toggle_category(cat_id):
    cat = ServiceCategory.query.get_or_404(cat_id)
    cat.is_active = not cat.is_active
    db.session.commit()
    return redirect(url_for("admin.categories"))


@admin_bp.route("/categories/<int:cat_id>/set-department", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR)
def set_category_department(cat_id):
    cat = ServiceCategory.query.get_or_404(cat_id)
    cat.department_id = request.form.get("department_id") or None
    log_action("update", "ServiceCategory", entity_id=cat.id,
               details=f"department_id={cat.department_id}")
    db.session.commit()
    flash(f"{cat.name_uz} — bo'lim yangilandi.", "success")
    return redirect(url_for("admin.categories"))


# ---------------------------------------------------------------------------
# Xodimlar / Ijrochilar
# ---------------------------------------------------------------------------
@admin_bp.route("/staff", methods=["GET", "POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR)
def staff():
    if request.method == "POST":
        password = request.form.get("password") or secrets.token_urlsafe(9)
        errors = validate_password_strength(password, current_app.config.get("PASSWORD_MIN_LENGTH", 8))
        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(url_for("admin.staff"))

        user = User(
            full_name=request.form["full_name"],
            username=request.form["username"],
            role=request.form["role"],
            phone=request.form.get("phone"),
            telegram_id=request.form.get("telegram_id") or None,
            department_id=request.form.get("department_id") or None,
            position=request.form.get("position"),
        )
        user.set_password(password)
        db.session.add(user)
        log_action("create", "User", details=user.username)
        db.session.commit()
        flash(f"Xodim yaratildi. Vaqtinchalik parol: {password}", "success")
        return redirect(url_for("admin.staff"))

    users = User.query.order_by(User.created_at.desc()).all()
    departments = Department.query.all()
    buildings = Building.query.all()
    roles = list(RoleEnum)
    return render_template("admin/staff.html", users=users, departments=departments,
                            buildings=buildings, roles=roles)


@admin_bp.route("/staff/<int:user_id>/toggle", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR)
def toggle_staff(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active_flag = not user.is_active_flag
    db.session.commit()
    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/<int:user_id>/set-departments", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR)
def set_staff_departments(user_id):
    """Ijrochini bir nechta yo'nalishga (bo'limga) biriktirish — masalan
    'Santexnika va Elektr' + 'Konditsioner'."""
    user = User.query.get_or_404(user_id)
    dept_ids = [int(d) for d in request.form.getlist("department_ids")]
    user.departments = Department.query.filter(Department.id.in_(dept_ids)).all() if dept_ids else []
    log_action("update", "User", entity_id=user.id, details=f"department_ids={dept_ids}")
    db.session.commit()
    flash(f"{user.full_name} — yo'nalishlari yangilandi.", "success")
    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/<int:user_id>/set-department", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR)
def set_staff_department(user_id):
    user = User.query.get_or_404(user_id)
    user.department_id = request.form.get("department_id") or None
    log_action("update", "User", entity_id=user.id, details=f"department_id={user.department_id}")
    db.session.commit()
    flash(f"{user.full_name} — bo'lim (yo'nalish) yangilandi.", "success")
    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/<int:user_id>/set-buildings", methods=["POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR)
def set_staff_buildings(user_id):
    """Ijrochini bir nechta binoga biriktirish — masalan Markaziy Apparat + Minor."""
    user = User.query.get_or_404(user_id)
    building_ids = [int(b) for b in request.form.getlist("building_ids")]
    user.buildings = Building.query.filter(Building.id.in_(building_ids)).all() if building_ids else []
    log_action("update", "User", entity_id=user.id, details=f"building_ids={building_ids}")
    db.session.commit()
    flash(f"{user.full_name} — binolari yangilandi.", "success")
    return redirect(url_for("admin.staff"))


# ---------------------------------------------------------------------------
# Bo'limlar
# ---------------------------------------------------------------------------
@admin_bp.route("/departments", methods=["GET", "POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR)
def departments():
    if request.method == "POST":
        dep = Department(name=request.form["name"], description=request.form.get("description"))
        db.session.add(dep)
        db.session.commit()
        flash("Bo'lim qo'shildi.", "success")
        return redirect(url_for("admin.departments"))

    deps = Department.query.all()
    return render_template("admin/departments.html", departments=deps)


@admin_bp.route("/buildings", methods=["GET", "POST"])
@login_required
@roles_required(RoleEnum.SUPER_ADMIN, RoleEnum.ADMINISTRATOR)
def buildings():
    if request.method == "POST":
        b = Building(name=request.form["name"], description=request.form.get("description"))
        db.session.add(b)
        db.session.commit()
        flash("Bino qo'shildi.", "success")
        return redirect(url_for("admin.buildings"))

    blds = Building.query.all()
    return render_template("admin/buildings.html", buildings=blds)


@admin_bp.route("/audit-log")
@login_required
@roles_required(RoleEnum.SUPER_ADMIN)
def audit_log():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(300).all()
    return render_template("admin/audit_log.html", logs=logs)
