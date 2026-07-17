"""
Sun'iy intellekt integratsiya moduli.

TZ p.13 ga muvofiq quyidagi imkoniyatlarni ta'minlaydi:
- murojaat matnini tahlil qilish
- avtomatik kategoriyani aniqlash
- ustuvorlikni belgilash
- avtomatik javob (draft) tayyorlash
- kechikish prognozlari (statistik yondashuv)
- rahbar uchun xulosalar tayyorlash

Standart provayder — Anthropic (Claude). config.AI_PROVIDER orqali
kelajakda OpenAI / Azure OpenAI / mahalliy LLM ga almashtirish mumkin.
"""
import json
import logging
from datetime import datetime, timedelta

from flask import current_app

logger = logging.getLogger(__name__)

CATEGORY_JSON_SYSTEM_PROMPT = """Sen kommunal va xo'jalik xizmatlari markazi uchun ishlaydigan yordamchi \
sun'iy intellektsan. Foydalanuvchi murojaatini tahlil qilib, FAQAT quyidagi JSON formatida javob ber, \
hech qanday qo'shimcha matn, izoh yoki markdown belgisi qo'shma:

{
  "category_name": "eng mos kategoriya nomi (berilgan ro'yxatdan)",
  "priority": "shoshilinch" | "yuqori" | "orta" | "past",
  "summary": "murojaatning 1-2 gapli qisqacha xulosasi (o'zbek tilida)",
  "draft_reply": "mijozga yuboriladigan qisqa, xushmuomala dastlabki javob matni (o'zbek tilida)"
}
"""


def _get_client():
    """Anthropic client obyektini qaytaradi, agar API kaliti sozlanmagan bo'lsa None qaytaradi."""
    api_key = current_app.config.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY sozlanmagan — AI funksiyalari o'chirilgan.")
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logger.error("anthropic paketi o'rnatilmagan (pip install anthropic).")
        return None


def analyze_request_text(description: str, categories: list) -> dict | None:
    """
    Murojaat matnini tahlil qilib, kategoriya/ustuvorlik/xulosa/dastlabki javobni qaytaradi.
    `categories` — ServiceCategory obyektlar ro'yxati.
    Xatolik yoki API kaliti yo'q bo'lsa None qaytaradi (chaqiruvchi kod buni handle qiladi).
    """
    client = _get_client()
    if client is None:
        return None

    category_names = [c.name_uz for c in categories]
    user_prompt = (
        f"Mavjud kategoriyalar: {', '.join(category_names)}\n\n"
        f"Mijoz murojaati:\n\"\"\"\n{description}\n\"\"\""
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=CATEGORY_JSON_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text_block = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        data = json.loads(text_block.strip().strip("`"))

        category_id = None
        for c in categories:
            if c.name_uz.strip().lower() == data.get("category_name", "").strip().lower():
                category_id = c.id
                break

        priority = data.get("priority") if data.get("priority") in (
            "shoshilinch", "yuqori", "orta", "past"
        ) else None

        return {
            "category_id": category_id,
            "priority": priority,
            "summary": data.get("summary"),
            "draft_reply": data.get("draft_reply"),
        }
    except Exception as exc:  # noqa: BLE001 — AI xizmati ishlamasa, tizim to'xtab qolmasligi kerak
        logger.exception("AI tahlili muvaffaqiyatsiz tugadi: %s", exc)
        return None


def correct_medicine_or_free_text(raw_text: str) -> str:
    """Umumiy maqsadli matn tuzatish yordamchisi (imlo xatolarini tuzatish, aniqlashtirish)."""
    client = _get_client()
    if client is None:
        return raw_text
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system="Foydalanuvchi matnidagi imlo xatolarini tuzat, ma'noni o'zgartirma. "
                   "Faqat tuzatilgan matnni qaytar, izoh berma.",
            messages=[{"role": "user", "content": raw_text}],
        )
        return "".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()
    except Exception:
        logger.exception("Matn tuzatishda xatolik.")
        return raw_text


def predict_delay_risk(category, current_open_count: int, avg_completion_hours: float, sla_hours: int) -> dict:
    """
    Statistik/evristik kechikish prognozi. To'liq ML modeli o'rniga tez ishlaydigan
    qoida-asosidagi baholash — production'da tarixiy ma'lumotlar bilan ML modeliga almashtiriladi.
    """
    if sla_hours <= 0:
        sla_hours = 24

    load_factor = min(current_open_count / 10.0, 1.0)  # ko'p ochiq ish -> kechikish xavfi oshadi
    time_factor = min(avg_completion_hours / sla_hours, 2.0) / 2.0

    risk_score = round((0.5 * load_factor + 0.5 * time_factor) * 100, 1)

    if risk_score >= 70:
        level = "yuqori"
    elif risk_score >= 40:
        level = "o'rta"
    else:
        level = "past"

    return {"risk_score": risk_score, "risk_level": level}


def generate_manager_insights(stats: dict) -> str | None:
    """
    Rahbar uchun umumiy statistika asosida qisqa, tabiiy tildagi xulosa tayyorlaydi.
    `stats` — dashboard/reports modulidan olingan agregatsiyalangan ko'rsatkichlar lug'ati.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system="Sen korxona rahbari uchun ishlaydigan analitik yordamchisan. Berilgan statistika "
                   "asosida 3-5 ta qisqa, aniq va amaliy xulosa/tavsiya yoz (o'zbek tilida, punktlar bilan).",
            messages=[{"role": "user", "content": json.dumps(stats, ensure_ascii=False, default=str)}],
        )
        return "".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()
    except Exception:
        logger.exception("Rahbar xulosalarini generatsiya qilishda xatolik.")
        return None
