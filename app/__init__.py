import os
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from app.extensions import db, login_manager, migrate, cors, csrf, limiter, cache, compress


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Railway/Nginx kabi teskari-proksi ortida ishga tushirilganda, proksi qo'shgan
    # X-Forwarded-* header'lariga ishonib, so'rovning haqiqiy sxema/klient IP'sini
    # tiklaydi — aks holda rate-limiter va audit jurnali proksi IP'sini ko'rar edi.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    csrf.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)
    compress.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.dispatcher.routes import dispatcher_bp
    from app.dashboard.routes import dashboard_bp
    from app.api.routes import api_bp
    from app.reports.routes import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(dispatcher_bp, url_prefix="/dispatcher")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    # Botlar X-Internal-Token orqali (sessiya/cookie'siz) autentifikatsiya qiladi,
    # shuning uchun brauzer-sessiyasiga mo'ljallangan CSRF tekshiruvi ularga tegishli emas.
    csrf.exempt(api_bp)

    from app.api.v1 import api_v1_bp
    app.register_blueprint(api_v1_bp, url_prefix="/api/v1")
    # v1 API JWT (Bearer token) orqali autentifikatsiya qiladi, sessiya cookie'siga
    # tayanmaydi — shuning uchun CSRF tekshiruvi bu yerga ham tegishli emas.
    csrf.exempt(api_v1_bp)

    from flasgger import Swagger
    app.config["SWAGGER"] = {
        "title": "Xizmat Platformasi API",
        "uiversion": 3,
        "specs_route": "/apidocs/",
    }
    Swagger(app, template={
        "securityDefinitions": {
            "BearerAuth": {"type": "apiKey", "name": "Authorization", "in": "header"}
        },
        "info": {
            "title": "Xizmat Platformasi API v1",
            "description": "JWT bilan himoyalangan versiyalangan API (mobil ilova va tashqi integratsiyalar uchun).",
            "version": "1.0.0",
        },
    })

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'"
        )
        if app.config.get("FORCE_HTTPS"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.context_processor
    def inject_globals():
        import random
        from datetime import datetime
        bg_scenes = ["cyber1.svg", "cyber2.svg", "cyber3.svg", "cyber4.svg", "cyber5.svg", "cyber6.svg", "cyber7.svg"]
        return {"now": datetime.utcnow(), "bg_scene": random.choice(bg_scenes)}

    from app.monitoring import init_monitoring
    init_monitoring(app)

    return app
