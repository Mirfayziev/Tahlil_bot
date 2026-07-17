"""JWT access/refresh token yordamchilari (TZ v2, bo'lim 2: API)."""
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import request, jsonify, current_app, g

from app.models import User


def generate_access_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": "access",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=current_app.config["JWT_ACCESS_MINUTES"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def generate_refresh_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "type": "refresh",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=current_app.config["JWT_REFRESH_DAYS"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])


def jwt_required(f):
    """Berilgan Authorization: Bearer <access_token> ni tekshiradi va
    g.current_user ga foydalanuvchini joylaydi."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization: Bearer <token> talab qilinadi"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                return jsonify({"error": "noto'g'ri token turi"}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token muddati tugagan"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "token yaroqsiz"}), 401

        user = User.query.get(int(payload["sub"]))
        if not user or not user.is_active_flag:
            return jsonify({"error": "foydalanuvchi topilmadi yoki bloklangan"}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return wrapped
