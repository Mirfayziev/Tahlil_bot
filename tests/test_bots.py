"""Bot yordamchi (pure) funksiyalari testlari.

To'liq aiogram Dispatcher/Telegram integratsiyasini test qilish alohida event-loop va
mock transport talab qiladi; bu yerda haqiqiy ishlaydigan, izolyatsiyalanган mantiq —
xabar formatlash va HTTP klient — tekshiriladi.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bots.executor_bot import _format_task
from bots.api_client import ApiClient


def test_format_task_includes_key_fields():
    task = {
        "number": "REQ-2026-000123", "category": "Santexnika", "priority": "yuqori",
        "description": "Kran buzilgan", "org_display": "Moliya / Hisob-kitob (xona 215)",
        "building": "Markaziy Apparat", "deadline_at": "2026-07-20T10:00:00",
        "status": "ijrochiga_yuborildi",
    }
    text = _format_task(task)
    assert "REQ-2026-000123" in text
    assert "Santexnika" in text
    assert "Markaziy Apparat" in text
    assert "Kran buzilgan" in text
    assert "yuqori" in text


def test_format_task_handles_missing_optional_fields():
    task = {
        "number": "REQ-2026-000124", "category": "Mebel", "priority": None,
        "description": "Stul kerak", "org_display": None, "address": None,
        "building": None, "deadline_at": None, "status": "yangi",
    }
    text = _format_task(task)
    assert "REQ-2026-000124" in text
    assert "Muddat: -" in text
    assert "Bino: -" in text


def test_api_client_builds_correct_urls():
    client = ApiClient(base_url="http://testserver/api")
    assert client.base_url == "http://testserver/api"


def test_api_client_strips_trailing_slash():
    client = ApiClient(base_url="http://testserver/api/")
    assert client.base_url == "http://testserver/api"
