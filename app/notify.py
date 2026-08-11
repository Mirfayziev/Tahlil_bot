"""
Zudlik bilan Telegram orqali bildirishnoma yuborish moduli.

Veb-platformada biror hodisa (yangi murojaat, tayinlash, holat o'zgarishi va h.k.)
yuz berganda, ushbu modul orqali tegishli foydalanuvchiga DARHOL Telegram xabari yuboriladi
(alohida notifier.py workerini kutmasdan). Notification jadvali baribir audit/tarix uchun saqlanadi.
"""
import logging
import mimetypes
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


def _telegram_file_path(token: str, file_id: str):
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id}, timeout=10
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("result", {}).get("file_path")
    except Exception:
        logger.exception("Telegram getFile so'rovida xatolik")
        return None


def download_telegram_file(token: str, file_id: str):
    """Telegram fayl (masalan rasm)ni bot API orqali yuklab oladi.
    Qaytaradi: (bytes, content_type) yoki xato bo'lsa (None, None)."""
    if not token or not file_id:
        return None, None
    file_path = _telegram_file_path(token, file_id)
    if not file_path:
        return None, None
    try:
        resp = requests.get(f"https://api.telegram.org/file/bot{token}/{file_path}", timeout=20)
        if resp.status_code != 200:
            return None, None
        # Telegramning fayl serveri ko'pincha aniq Content-Type qaytarmaydi
        # (application/octet-stream), shuning uchun fayl kengaytmasidan aniqlaymiz.
        content_type = resp.headers.get("Content-Type")
        if not content_type or content_type == "application/octet-stream":
            guessed, _ = mimetypes.guess_type(file_path)
            content_type = guessed or content_type or "application/octet-stream"
        return resp.content, content_type
    except Exception:
        logger.exception("Telegram fayl yuklab olishda xatolik")
        return None, None


def send_telegram_photo(token: str, chat_id: str, file_id: str, caption: str = None,
                         source_token: str = None) -> bool:
    """
    Rasmni Telegram orqali yuboradi. Telegram file_id'lar botlar orasida ishlamaydi —
    agar rasm boshqa bot orqali yuklangan bo'lsa (source_token != token), avval manba
    bot orqali fayl baytlari yuklab olinadi va maqsad botga qayta yuklab yuboriladi.
    """
    if not token or not chat_id or not file_id:
        return False
    try:
        if not source_token or source_token == token:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                json={"chat_id": chat_id, "photo": file_id, "caption": caption or ""},
                timeout=15,
            )
        else:
            content, _ = download_telegram_file(source_token, file_id)
            if not content:
                return False
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                data={"chat_id": chat_id, "caption": caption or ""},
                files={"photo": ("photo.jpg", content)},
                timeout=25,
            )
        if resp.status_code != 200:
            logger.warning("Telegram rasm yuborishda xato: %s — %s", resp.status_code, resp.text[:200])
        return resp.status_code == 200
    except Exception:
        logger.exception("Telegramga rasm yuborishda xatolik")
        return False


def _try_send_email(to_email: str, subject: str, body: str):
    """Email — qo'shimcha kanal (TZ v2, bo'lim 4). Telegram asosiy hisoblanadi,
    shuning uchun bu yerda xatolik asosiy oqimni buzmasligi kerak."""
    try:
        from app.email_utils import send_email
        send_email([to_email], subject, body)
    except Exception:
        logger.exception("Email orqali bildirishnoma yuborishda xatolik: %s", to_email)


def notify(recipient_type: str, recipient_id: int, message: str, reply_markup: dict = None,
           photo_file_id: str = None):
    """
    Notification yozuvini yaratadi VA imkon bo'lsa Telegram orqali zudlik bilan yuboradi.
    recipient_type: "customer" | "executor" | "dispatcher"
    reply_markup: ixtiyoriy — Telegram inline keyboard (masalan baholash tugmalari uchun).
    photo_file_id: ixtiyoriy — murojaatchi (customer bot) yuklagan rasm file_id'si; berilsa
    ijrochiga xabar shu rasm bilan birga (caption sifatida `message` bilan) yuboriladi.
    """
    from app.extensions import db
    from app.models import Notification, Customer, User

    notif = Notification(
        recipient_type=recipient_type, recipient_id=recipient_id, message=message,
        reply_markup=reply_markup,
    )
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
                executor_token = current_app.config.get("EXECUTOR_BOT_TOKEN")
                if photo_file_id:
                    ok = send_telegram_photo(
                        executor_token, user.telegram_id, photo_file_id, caption=message,
                        source_token=current_app.config.get("CUSTOMER_BOT_TOKEN"),
                    )
                else:
                    ok = send_telegram_message(executor_token, user.telegram_id, message)
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
