"""Email yuborish yordamchisi (TZ v2, bo'lim 4: Bildirishnomalar)."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

logger = logging.getLogger(__name__)


def send_email(to: list[str], subject: str, body: str, html_body: str = None) -> bool:
    """SMTP orqali email yuboradi. MAIL_SERVER sozlanmagan bo'lsa, jim o'tkazib yuboradi
    (mahalliy/dev muhitda email provayder bo'lmasligi mumkin — bu kutilgan holat)."""
    server = current_app.config.get("MAIL_SERVER")
    if not server or not to:
        logger.info("MAIL_SERVER sozlanmagan yoki qabul qiluvchi yo'q — email yuborilmadi.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = current_app.config.get("MAIL_FROM")
    msg["To"] = ", ".join(to)
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(server, current_app.config.get("MAIL_PORT", 587), timeout=10) as smtp:
            if current_app.config.get("MAIL_USE_TLS"):
                smtp.starttls()
            username = current_app.config.get("MAIL_USERNAME")
            password = current_app.config.get("MAIL_PASSWORD")
            if username and password:
                smtp.login(username, password)
            smtp.sendmail(msg["From"], to, msg.as_string())
        return True
    except Exception:
        logger.exception("Email yuborishda xatolik: %s", subject)
        return False
