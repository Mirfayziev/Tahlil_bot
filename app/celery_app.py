"""Celery ilovasi (TZ v2, bo'lim 3: DevOps).

Production muhitida notifier.py o'rniga shu Celery Beat jadvali ishlatiladi —
Redis broker orqali, alohida worker va beat processlarida.

Ishga tushirish:
    celery -A app.celery_app.celery_app worker --loglevel=info
    celery -A app.celery_app.celery_app beat --loglevel=info
"""
from celery import Celery
from celery.schedules import crontab

from config import Config


def make_celery() -> Celery:
    celery_app = Celery(
        "service_platform",
        broker=Config.REDIS_URL,
        backend=Config.REDIS_URL,
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        beat_schedule={
            "scan-deadlines-every-minute": {
                "task": "app.tasks.scan_deadlines_task",
                "schedule": 60.0,
            },
            "run-auto-assign-every-minute": {
                "task": "app.tasks.run_auto_assign_task",
                "schedule": 60.0,
            },
            "process-pending-notifications-every-15s": {
                "task": "app.tasks.process_pending_notifications_task",
                "schedule": 15.0,
            },
            "generate-daily-report-at-7am": {
                "task": "app.tasks.generate_scheduled_report_task",
                "schedule": crontab(hour=7, minute=0),
            },
        },
    )

    class ContextTask(celery_app.Task):
        """Har bir task Flask app_context ichida ishga tushadi (DB va config uchun).
        Agar chaqiruvchi tomonda allaqachon app_context faol bo'lsa (masalan testlarda),
        o'shani ishlatadi — yangi (bo'sh, standart config'li) ilova yaratmaydi."""
        def __call__(self, *args, **kwargs):
            from flask import has_app_context
            if has_app_context():
                return self.run(*args, **kwargs)
            from app import create_app
            app = create_app()
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
    return celery_app


celery_app = make_celery()

# Task'larni ro'yxatdan o'tkazish uchun import qilinadi.
from app import tasks  # noqa: E402,F401
