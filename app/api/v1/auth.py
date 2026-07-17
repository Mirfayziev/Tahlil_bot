"""JWT autentifikatsiya endpointlari — /api/v1/auth/* (TZ v2, bo'lim 2: API)."""
import jwt as pyjwt
from flask import request, jsonify, g

from app.api.v1 import api_v1_bp
from app.api.v1.jwt_utils import generate_access_token, generate_refresh_token, decode_token, jwt_required
from app.api.v1.schemas import LoginSchema, RefreshSchema
from app.extensions import limiter
from app.models import User


@api_v1_bp.route("/auth/login", methods=["POST"])
@limiter.limit("10 per minute")
def v1_login():
    """
    Login (JWT access + refresh token oladi)
    ---
    tags: [Auth]
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [username, password]
          properties:
            username: {type: string}
            password: {type: string}
    responses:
      200:
        description: access_token, refresh_token va foydalanuvchi ma'lumoti
      401:
        description: login yoki parol noto'g'ri, yoki hisob bloklangan
      422:
        description: validatsiya xatosi
    """
    data = request.get_json(silent=True) or {}
    errors = LoginSchema().validate(data)
    if errors:
        return jsonify({"errors": errors}), 422

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not user.check_password(data["password"]) or not user.is_active_flag:
        return jsonify({"error": "login yoki parol noto'g'ri"}), 401
    if user.is_locked:
        return jsonify({"error": "hisob vaqtincha bloklangan"}), 423

    return jsonify({
        "access_token": generate_access_token(user),
        "refresh_token": generate_refresh_token(user),
        "user": {"id": user.id, "full_name": user.full_name, "role": user.role.value},
    })


@api_v1_bp.route("/auth/refresh", methods=["POST"])
@limiter.limit("30 per minute")
def v1_refresh():
    """
    Refresh token orqali yangi access token olish
    ---
    tags: [Auth]
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [refresh_token]
          properties:
            refresh_token: {type: string}
    responses:
      200:
        description: yangi access_token
      401:
        description: refresh token yaroqsiz yoki muddati tugagan
    """
    data = request.get_json(silent=True) or {}
    errors = RefreshSchema().validate(data)
    if errors:
        return jsonify({"errors": errors}), 422

    try:
        payload = decode_token(data["refresh_token"])
        if payload.get("type") != "refresh":
            return jsonify({"error": "noto'g'ri token turi"}), 401
    except pyjwt.ExpiredSignatureError:
        return jsonify({"error": "refresh token muddati tugagan — qayta login qiling"}), 401
    except pyjwt.InvalidTokenError:
        return jsonify({"error": "token yaroqsiz"}), 401

    user = User.query.get(int(payload["sub"]))
    if not user or not user.is_active_flag:
        return jsonify({"error": "foydalanuvchi topilmadi"}), 401
    return jsonify({"access_token": generate_access_token(user)})


@api_v1_bp.route("/auth/me", methods=["GET"])
@jwt_required
def v1_me():
    """
    Joriy foydalanuvchi ma'lumoti
    ---
    tags: [Auth]
    security: [{BearerAuth: []}]
    responses:
      200:
        description: foydalanuvchi ma'lumoti
      401:
        description: token yo'q yoki yaroqsiz
    """
    u = g.current_user
    return jsonify({
        "id": u.id, "full_name": u.full_name, "username": u.username,
        "role": u.role.value, "phone": u.phone,
    })
