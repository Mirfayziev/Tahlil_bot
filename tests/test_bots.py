"""Bot yordamchi (pure) funksiyalari testlari.

To'liq aiogram Dispatcher/Telegram integratsiyasini test qilish alohida event-loop va
mock transport talab qiladi; bu yerda haqiqiy ishlaydigan, izolyatsiyalanган mantiq —
xabar formatlash va HTTP klient — tekshiriladi.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bots.executor_bot import _format_task, _task_keyboard, _task_stage
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


def test_task_stage_detection():
    assert _task_stage({"response": None}) == "pending"
    assert _task_stage({"response": "qabul_qilindi", "started_at": None}) == "accepted"
    assert _task_stage({"response": "qabul_qilindi", "started_at": "2026-07-20T10:00:00"}) == "in_progress"


def test_task_keyboard_buttons_carry_the_correct_assignment_id():
    """Har bir topshiriqning tugmalari FAQAT o'ziga tegishli assignment_id'ni
    o'z ichiga olishi kerak - aks holda bir nechta topshiriq bir vaqtda
    ko'rsatilganda ular bir-birining tugmalarini bosib qolishi mumkin edi
    (avvalgi bug: reply-klaviatura butun chat uchun umumiy edi)."""
    kb_pending = _task_keyboard(42, "pending")
    callbacks = [btn.callback_data for row in kb_pending.inline_keyboard for btn in row]
    assert callbacks == ["acc:42", "rej:42"]

    kb_accepted = _task_keyboard(42, "accepted")
    callbacks = [btn.callback_data for row in kb_accepted.inline_keyboard for btn in row]
    assert callbacks == ["beg:42", "nfo:42"]

    kb_in_progress = _task_keyboard(42, "in_progress")
    callbacks = [btn.callback_data for row in kb_in_progress.inline_keyboard for btn in row]
    assert callbacks == ["cmp:42", "ext:42", "nfo:42"]


def test_task_keyboards_for_different_tasks_never_collide():
    kb_a = _task_keyboard(1, "pending")
    kb_b = _task_keyboard(2, "pending")
    callbacks_a = {btn.callback_data for row in kb_a.inline_keyboard for btn in row}
    callbacks_b = {btn.callback_data for row in kb_b.inline_keyboard for btn in row}
    assert callbacks_a.isdisjoint(callbacks_b)
