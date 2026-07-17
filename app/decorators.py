from functools import wraps
from flask import abort
from flask_login import current_user


def roles_required(*roles):
    """Faqat ko'rsatilgan rollarga ega foydalanuvchilarga ruxsat beradi."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def internal_api_required(f):
    """Telegram botlar tomonidan chaqiriladigan ichki API endpointlarini himoya qiladi."""
    from flask import request, current_app, jsonify

    @wraps(f)
    def wrapped(*args, **kwargs):
        token = request.headers.get("X-Internal-Token")
        if token != current_app.config["INTERNAL_API_TOKEN"]:
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapped
