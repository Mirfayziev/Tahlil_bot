from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db, limiter
from app.models import User, RoleEnum, AuditLog

auth_bp = Blueprint("auth", __name__)


def _log_auth(action, user_id=None, details=None):
    db.session.add(AuditLog(user_id=user_id, action=action, entity="auth", details=details))
    db.session.commit()


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user and user.is_locked:
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
            flash(f"Hisob vaqtincha bloklangan. {remaining} daqiqadan so'ng qayta urinib ko'ring.", "danger")
            _log_auth("login_blocked", user_id=user.id, details=f"username={username}")
            return render_template("auth/login.html")

        if user and user.check_password(password) and user.is_active_flag:
            user.failed_login_count = 0
            user.locked_until = None
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            login_user(user)
            _log_auth("login_success", user_id=user.id)
            flash(f"Xush kelibsiz, {user.full_name}!", "success")
            return redirect(url_for("dashboard.index"))

        if user:
            max_attempts = current_app.config.get("LOGIN_MAX_ATTEMPTS", 5)
            lockout_minutes = current_app.config.get("LOGIN_LOCKOUT_MINUTES", 15)
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= max_attempts:
                user.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
                db.session.commit()
                _log_auth("login_lockout", user_id=user.id, details=f"attempts={user.failed_login_count}")
                flash(
                    f"Ko'p marta noto'g'ri urinish sabab hisob {lockout_minutes} daqiqaga bloklandi.",
                    "danger",
                )
                return render_template("auth/login.html")
            db.session.commit()

        _log_auth("login_failed", user_id=user.id if user else None, details=f"username={username}")
        flash("Login yoki parol noto'g'ri.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    _log_auth("logout", user_id=current_user.id)
    logout_user()
    flash("Tizimdan chiqdingiz.", "info")
    return redirect(url_for("auth.login"))
