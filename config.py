import os
from datetime import timedelta
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'local.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Xavfsizlik (TZ v2, bo'lim 1) ---
    # Production'da HTTPS ortida ishlatilganda FORCE_HTTPS=true qiling — shunda
    # sessiya cookie'si faqat HTTPS orqali yuboriladi va HSTS header yoqiladi.
    FORCE_HTTPS = os.environ.get("FORCE_HTTPS", "false").lower() == "true"
    SESSION_COOKIE_SECURE = FORCE_HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = FORCE_HTTPS
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Kuchli parol siyosati
    PASSWORD_MIN_LENGTH = int(os.environ.get("PASSWORD_MIN_LENGTH", "8"))

    # Login himoyasi: N marta noto'g'ri urinishdan so'ng hisob vaqtincha bloklanadi
    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15"))

    # JWT (tashqi/mobil API uchun, TZ v2 bo'lim 2)
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_MINUTES = int(os.environ.get("JWT_ACCESS_MINUTES", "30"))
    JWT_REFRESH_DAYS = int(os.environ.get("JWT_REFRESH_DAYS", "30"))

    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Login/API rate-limiting hisoblagichi qayerda saqlanadi. Default — jarayon xotirasi
    # (Redis shart emas), lekin bir nechta gunicorn worker/instansiya ishlatilsa (masalan
    # Railway/production'da) worker'lar orasida limit ulashilmaydi — shu holatda
    # RATELIMIT_STORAGE_URI=redis://... qiling.
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    INTERNAL_API_TOKEN = os.environ.get("INTERNAL_API_TOKEN", "dev-internal-token")

    CUSTOMER_BOT_TOKEN = os.environ.get("CUSTOMER_BOT_TOKEN", "")
    EXECUTOR_BOT_TOKEN = os.environ.get("EXECUTOR_BOT_TOKEN", "")
    NOTIFY_BOT_TOKEN = os.environ.get("NOTIFY_BOT_TOKEN", "")

    WEB_API_BASE_URL = os.environ.get("WEB_API_BASE_URL", "http://localhost:5000/api")

    AI_PROVIDER = os.environ.get("AI_PROVIDER", "anthropic")
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(basedir, "uploads"))
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB

    # SLA sozlamalari (soatlarda), устуворлик даражасига қараб
    SLA_HOURS = {
        "past": 2,       # шошилинч
        "yuqori": 8,     # юқори
        "orta": 24,      # ўрта
        "past_emas": 72  # паст
    }

    # AI avtomatik yo'naltirish: dispetcher ma'lum vaqt ichida murojaatni qabul qilmasa,
    # AI o'zi kategoriya bo'yicha tegishli bo'limdagi eng bo'sh ijrochiga avtomatik yuboradi.
    AUTO_ASSIGN_ENABLED = os.environ.get("AUTO_ASSIGN_ENABLED", "true").lower() == "true"
    AUTO_ASSIGN_AFTER_MINUTES = int(os.environ.get("AUTO_ASSIGN_AFTER_MINUTES", "15"))

    # Email (TZ v2, bo'lim 4: Bildirishnomalar va bo'lim 7: rejalashtirilgan hisobotlar)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "no-reply@service-platform.local")
    MAIL_ADMIN_RECIPIENTS = [
        e.strip() for e in os.environ.get("MAIL_ADMIN_RECIPIENTS", "").split(",") if e.strip()
    ]

    # SMS (TZ v2, bo'lim 4: Bildirishnomalar) — Eskiz.uz kabi mahalliy provayder uchun tayyor joy
    SMS_PROVIDER_URL = os.environ.get("SMS_PROVIDER_URL", "")
    SMS_API_KEY = os.environ.get("SMS_API_KEY", "")

    # --- Performance (TZ v2, bo'lim 5) ---
    # Dashboard'dagi og'ir agregatsiya so'rovlari (summary/top-categories/top-executors/...)
    # qisqa muddatga keshlanadi — real vaqt talab qilinmaydigan hisobot xarakteridagi
    # endpointlar uchun DB yukini kamaytiradi.
    # Lokal ishga tushirishda (Redis serversiz) ham ishlashi uchun default — jarayon
    # xotirasidagi SimpleCache. Productionda (Docker-compose, Redis konteyneri bilan)
    # CACHE_TYPE=RedisCache qiling — shunda bir nechta gunicorn worker orasida kesh ulashiladi.
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "SimpleCache")
    CACHE_REDIS_URL = os.environ.get("CACHE_REDIS_URL", REDIS_URL)
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", "30"))

    # HTML/JSON javoblarni gzip bilan siqish (Flask-Compress)
    COMPRESS_MIMETYPES = [
        "text/html", "text/css", "text/xml", "application/json",
        "application/javascript", "text/javascript",
    ]
    COMPRESS_MIN_SIZE = 500
