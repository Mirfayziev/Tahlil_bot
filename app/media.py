"""
Telegramda yuklangan fayllarni (rasm/video) veb-interfeys uchun proksi qiladi.

Telegram file_id fayli faqat mos bot tokeni orqali yuklab olinishi mumkin, shuning
uchun tokenni frontendga oshkor qilmaslik uchun bu yerda serverda proksi qilinadi.
"""
from flask import Blueprint, Response, abort, current_app
from flask_login import login_required

from app.models import RequestAttachment
from app.notify import download_telegram_file

media_bp = Blueprint("media", __name__)


def _token_for_attachment(att: RequestAttachment) -> str:
    if att.uploaded_by_type == "executor":
        return current_app.config.get("EXECUTOR_BOT_TOKEN")
    return current_app.config.get("CUSTOMER_BOT_TOKEN")


# Telegram foto/video fayl yo'llari odatda kengaytmasiz keladi (masalan "photos/file_0"),
# shuning uchun Telegram Content-Type qaytarmasa, o'zimiz saqlagan file_type'ga tayanamiz.
_DEFAULT_CONTENT_TYPE = {"photo": "image/jpeg", "video": "video/mp4"}


@media_bp.route("/telegram/<int:attachment_id>")
@login_required
def telegram_file(attachment_id):
    att = RequestAttachment.query.get_or_404(attachment_id)
    token = _token_for_attachment(att)
    content, content_type = download_telegram_file(token, att.file_ref)
    if content is None:
        abort(404)
    if not content_type or content_type == "application/octet-stream":
        content_type = _DEFAULT_CONTENT_TYPE.get(att.file_type, content_type or "application/octet-stream")
    return Response(
        content, mimetype=content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )
