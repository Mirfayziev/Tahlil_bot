"""
Zudlik bilan Telegram orqali bildirishnoma yuborish moduli.

Veb-platformada biror hodisa (yangi murojaat, tayinlash, holat o'zgarishi va h.k.)
yuz berganda, ushbu modul orqali tegishli foydalanuvchiga DARHOL Telegram xabari yuboriladi
(alohida notifier.py workerini kutmasdan). Notification jadvali baribir audit/tarix uchun saqlanadi.
"""
import logging
from datetime import datetime

import requests
from flask import current_app

logger = logging.getLogger(__name__)


def send_telegram_message(token: str, chat_id: str, text: str, reply_markup: dict = None) -> bool:
    if not token or not chat_id:
        return False
    try:
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning("Telegram API xato qaytardi: %s — %s", resp.status_code, resp.text[:200])
        return resp.status_code == 200
    except Exception:
        logger.exception("Telegramga xabar yuborishda xatolik")
        return False


def _try_send_email(to_email: str, subject: str, body: str):
    """Email — qo'shimcha kanal (TZ v2, bo'lim 4). Telegram asosiy hisoblanadi,
    shuning uchun bu yerda xatolik asosiy oqimni buzmasligi kerak."""
    try:
        from app.email_utils import send_email
        send_email([to_email], subject, body)
    except Exception:
        logger.exception("Email orqali bildirishnoma yuborishda xatolik: %s", to_email)


def notify(recipient_type: str, recipient_id: int, message: str, reply_markup: dict = None):
    """
    Notification yozuvini yaratadi VA imkon bo'lsa Telegram orqali zudlik bilan yuboradi.
    recipient_type: "customer" | "executor" | "dispatcher"
    reply_markup: ixtiyoriy — Telegram inline keyboard (masalan baholash tugmalari uchun).
    """
    from app.extensions import db
    from app.models import Notification, Customer, User

    notif = Notification(recipient_type=recipient_type, recipient_id=recipient_id, message=message)
    db.session.add(notif)

    ok = False
    try:
        if recipient_type == "customer":
            customer = Customer.query.get(recipient_id)
            if customer:
                ok = send_telegram_message(
                    current_app.config.get("CUSTOMER_BOT_TOKEN"), customer.telegram_id, message,
                    reply_markup=reply_markup,
                )
        elif recipient_type == "executor":
            user = User.query.get(recipient_id)
            if user and user.telegram_id:
                ok = send_telegram_message(
                    current_app.config.get("EXECUTOR_BOT_TOKEN"), user.telegram_id, message
                )
            if user and user.email:
                _try_send_email(user.email, "Xizmat platformasi — yangi bildirishnoma", message)
        elif recipient_type == "dispatcher":
            user = User.query.get(recipient_id)
            if user and user.telegram_id:
                token = current_app.config.get("NOTIFY_BOT_TOKEN") or current_app.config.get("EXECUTOR_BOT_TOKEN")
                ok = send_telegram_message(token, user.telegram_id, message)
            if user and user.email:
                _try_send_email(user.email, "Xizmat platformasi — yangi bildirishnoma", message)
    except Exception:
        logger.exception("Bildirishnoma yuborishda xatolik (recipient_type=%s, id=%s)", recipient_type, recipient_id)

    if ok:
        notif.is_sent = True
        notif.sent_at = datetime.utcnow()

    return notif
