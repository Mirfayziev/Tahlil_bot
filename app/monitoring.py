"""Monitoring va Health Check (TZ v2, bo'lim 3: DevOps)."""
import time

from flask import Blueprint, jsonify, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

monitoring_bp = Blueprint("monitoring", __name__)

REQUEST_COUNT = Counter(
    "http_requests_total", "Jami HTTP so'rovlar soni", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "So'rov davomiyligi (sekund)", ["endpoint"]
)


def init_monitoring(app):
    @app.before_request
    def _start_timer():
        from flask import g
        g._monitoring_start = time.time()

    @app.after_request
    def _record_metrics(response):
        from flask import g, request
        if request.path in ("/metrics", "/healthz"):
            return response
        endpoint = request.endpoint or "unknown"
        REQUEST_COUNT.labels(method=request.method, endpoint=endpoint, status=response.status_code).inc()
        started = getattr(g, "_monitoring_start", None)
        if started is not None:
            REQUEST_LATENCY.labels(endpoint=endpoint).observe(time.time() - started)
        return response

    app.register_blueprint(monitoring_bp)


@monitoring_bp.route("/healthz")
def healthz():
    """Docker/Nginx/Load-balancer uchun oddiy, autentifikatsiyasiz health check."""
    from app.extensions import db
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 503


@monitoring_bp.route("/metrics")
def metrics():
    """Prometheus formatidagi metrikalar."""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
