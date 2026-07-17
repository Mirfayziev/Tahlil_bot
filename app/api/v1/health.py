from flask import jsonify

from app.api.v1 import api_v1_bp
from app.extensions import db


@api_v1_bp.route("/health", methods=["GET"])
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return jsonify({"status": status, "db": db_ok}), (200 if db_ok else 503)
