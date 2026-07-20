"""
Bildirishnoma yuboruvchi fon jarayon (worker).

Vazifalari (TZ p.8):
- muddat tugashidan oldin ogohlantirish
- muddat o'tganda ogohlantirish
- yangi murojaat kelganda (Notification jadvaliga API tomonidan yoziladi)
- javob qaytganda (Notification jadvaliga API tomonidan yoziladi)

Bu skript Notification jadvalidagi yuborilmagan yozuvlarni Telegram orqali yuboradi
va muddatlarni skanerlab, yangi ogohlantirish yozuvlarini yaratadi.

Ishga tushirish (alohida process sifatida, doimiy ishlab turadi):
    python bots/notifier.py
"""
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

import aiohttp

from app import create_app
from app.extensions import db
from app.models import (
    Notification, Customer, User, RequestStatus, ServiceRequest, RoleEnum
)
from app.ai.auto_assign import auto_assign_pending_requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notifier")

CUSTOMER_BOT_TOKEN = os.environ.get("CUSTOMER_BOT_TOKEN", "")
EXECUTOR_BOT_TOKEN = os.environ.get("EXECUTOR_BOT_TOKEN", "")
NOTIFY_BOT_TOKEN = os.environ.get("NOTIFY_BOT_TOKEN", "")  # dispatcher/admin uchun

POLL_INTERVAL_SECONDS = 15
DEADLINE_WARNING_MINUTES_BEFORE = 60

app = create_app()


async def _send_telegram_message(token: str, chat_id: str, text: str, reply_markup: dict = None):
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return resp.status == 200


async def _dispatch_notification(notif: Notification) -> bool:
    if notif.recipient_type == "customer":
        customer = Customer.query.get(notif.recipient_id)
        if not customer:
            return False
        return await _send_telegram_message(
            CUSTOMER_BOT_TOKEN, customer.telegram_id, notif.message, notif.reply_markup
        )

    if notif.recipient_type == "executor":
        user = User.query.get(notif.recipient_id)
        if not user or not user.telegram_id:
            return False
        return await _send_telegram_message(
            EXECUTOR_BOT_TOKEN, user.telegram_id, notif.message, notif.reply_markup
        )

    if notif.recipient_type == "dispatcher":
        user = User.query.get(notif.recipient_id)
        if not user or not user.telegram_id:
            return False
        return await _send_telegram_message(
            NOTIFY_BOT_TOKEN or EXECUTOR_BOT_TOKEN, user.telegram_id, notif.message, notif.reply_markup
        )

    return False


async def process_pending_notifications():
    with app.app_context():
        pending = Notification.query.filter_by(is_sent=False).limit(100).all()
        for notif in pending:
            try:
                ok = await _dispatch_notification(notif)
                if ok:
                    notif.is_sent = True
                    notif.sent_at = datetime.utcnow()
            except Exception:
                logger.exception("Bildirishnoma yuborishda xatolik: %s", notif.id)
        db.session.commit()


async def scan_deadlines():
    """Muddati yaqinlashayotgan yoki o'tib ketgan murojaatlar uchun ogohlantirish yaratadi."""
    with app.app_context():
        open_statuses = [RequestStatus.NEW, RequestStatus.ACCEPTED, RequestStatus.SENT_TO_EXECUTOR,
                          RequestStatus.IN_PROGRESS, RequestStatus.WAITING_INFO]
        open_reqs = ServiceRequest.query.filter(ServiceRequest.status.in_(open_statuses)).all()
        now = datetime.utcnow()

        for r in open_reqs:
            if not r.deadline_at:
                continue

            executor = r.current_executor
            if not executor:
                continue

            already_warned = any(
                "muddat tugashiga" in (n.message or "") and n.recipient_id == executor.id
                for n in Notification.query.filter_by(recipient_type="executor", recipient_id=executor.id).all()
            )
            if (r.deadline_at - now) <= timedelta(minutes=DEADLINE_WARNING_MINUTES_BEFORE) and \
                    r.deadline_at > now and not already_warned:
                db.session.add(Notification(
                    recipient_type="executor", recipient_id=executor.id,
                    message=f"⏰ Diqqat! {r.number} bo'yicha muddat tugashiga "
                            f"{DEADLINE_WARNING_MINUTES_BEFORE} daqiqa qoldi."
                ))

            if r.deadline_at < now:
                already_overdue_notified = any(
                    "muddati o'tib ketdi" in (n.message or "") and n.recipient_id == executor.id
                    for n in Notification.query.filter_by(recipient_type="executor", recipient_id=executor.id).all()
                )
                if not already_overdue_notified:
                    db.session.add(Notification(
                        recipient_type="executor", recipient_id=executor.id,
                        message=f"🔴 {r.number} bo'yicha muddati o'tib ketdi! Iltimos, tezroq bajaring."
                    ))
                    dispatchers = User.query.filter(User.role.in_(
                        [RoleEnum.DISPATCHER, RoleEnum.ADMINISTRATOR])).all()
                    for d in dispatchers:
                        db.session.add(Notification(
                            recipient_type="dispatcher", recipient_id=d.id,
                            message=f"🔴 {r.number} muddati o'tib ketdi (ijrochi: {executor.full_name})."
                        ))

        db.session.commit()


async def run_auto_assign():
    """Dispetcher belgilangan vaqt ichida murojaatga javob bermasa, AI o'zi yo'naltiradi (TZ p.13)."""
    with app.app_context():
        auto_assign_pending_requests()


async def main_loop():
    logger.info("Bildirishnoma workeri ishga tushdi.")
    while True:
        await scan_deadlines()
        await run_auto_assign()
        await process_pending_notifications()
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main_loop())
