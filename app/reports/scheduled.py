"""Rejalashtirilgan (avtomatik) hisobotlar — Celery Beat orqali har kuni ishga tushadi
(TZ v2, bo'lim 7: Hisobotlar)."""
import logging
from datetime import datetime, timedelta

from flask import current_app

from app.models import ServiceRequest, RequestStatus, Rating
from app.email_utils import send_email

logger = logging.getLogger(__name__)


def generate_and_email_daily_report() -> dict:
    """O'tgan 24 soatlik faoliyat bo'yicha qisqa hisobot tuzib, MAIL_ADMIN_RECIPIENTS ga yuboradi."""
    since = datetime.utcnow() - timedelta(hours=24)

    new_count = ServiceRequest.query.filter(ServiceRequest.created_at >= since).count()
    done_count = ServiceRequest.query.filter(
        ServiceRequest.completed_at.isnot(None), ServiceRequest.completed_at >= since
    ).count()
    overdue_count = ServiceRequest.query.filter(
        ServiceRequest.deadline_at.isnot(None), ServiceRequest.deadline_at < datetime.utcnow(),
        ServiceRequest.status.notin_([RequestStatus.DONE, RequestStatus.CLOSED, RequestStatus.REJECTED]),
    ).count()
    ratings = Rating.query.filter(Rating.created_at >= since).all()
    avg_rating = round(sum(r.stars for r in ratings) / len(ratings), 2) if ratings else None

    body = (
        f"Kunlik hisobot — {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
        f"Yangi murojaatlar (24 soat): {new_count}\n"
        f"Bajarilgan murojaatlar (24 soat): {done_count}\n"
        f"Hozirda muddati o'tgan murojaatlar: {overdue_count}\n"
        f"O'rtacha baho (24 soat): {avg_rating if avg_rating is not None else '-'}\n"
    )

    recipients = current_app.config.get("MAIL_ADMIN_RECIPIENTS", [])
    sent = send_email(recipients, "Xizmat platformasi — kunlik hisobot", body) if recipients else False

    result = {
        "new_count": new_count, "done_count": done_count,
        "overdue_count": overdue_count, "avg_rating": avg_rating,
        "email_sent": sent, "recipients": recipients,
    }
    logger.info("Kunlik hisobot tayyorlandi: %s", result)
    return result
