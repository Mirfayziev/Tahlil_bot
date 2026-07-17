"""
Telegram Bot №1 — Istemolchilar uchun (TZ p.14).

Ishga tushirish:
    python bots/customer_bot.py
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, CallbackQuery
)

from bots.api_client import api_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("customer_bot")

BOT_TOKEN = os.environ.get("CUSTOMER_BOT_TOKEN", "")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

STATUS_LABELS = {
    "yangi": "🆕 Yangi",
    "qabul_qilindi": "✅ Qabul qilindi",
    "ijrochiga_yuborildi": "📤 Ijrochiga yuborildi",
    "bajarilmoqda": "🔧 Jarayonda",
    "qoshimcha_malumot_kutilmoqda": "❓ Qo'shimcha ma'lumot kutilmoqda",
    "bajarildi": "🎉 Bajarildi",
    "yopildi": "🔒 Yopildi",
    "rad_etildi": "❌ Rad etildi",
}

CANCEL_BTN = "❌ Bekor qilish"

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🆕 Yangi murojaat")],
        [KeyboardButton(text="📋 Mening murojaatlarim")],
        [KeyboardButton(text="ℹ️ Yordam")],
    ],
    resize_keyboard=True,
)

SKIP_MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⏭ O'tkazib yuborish")], [KeyboardButton(text=CANCEL_BTN)]],
    resize_keyboard=True,
)

PHONE_MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Telefon raqamni ulashish", request_contact=True)]],
    resize_keyboard=True,
)


class OnboardingFSM(StatesGroup):
    entering_phone = State()


class NewRequestFSM(StatesGroup):
    choosing_building = State()
    choosing_category = State()
    entering_comment = State()
    uploading_photo = State()
    uploading_video = State()
    entering_org_unit = State()


class RatingFSM(StatesGroup):
    choosing_stars = State()
    entering_feedback = State()
    entering_suggestion = State()


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    status, result = await api_client.upsert_customer(
        telegram_id=str(message.from_user.id),
        full_name=message.from_user.full_name,
        language=message.from_user.language_code or "uz",
    )

    if status == 200 and not result.get("phone"):
        await state.set_state(OnboardingFSM.entering_phone)
        await message.answer(
            "Assalomu alaykum! Xizmat ko'rsatish botiga xush kelibsiz.\n\n"
            "Davom etishdan oldin, iltimos telefon raqamingizni yuboring "
            "(pastdagi tugma orqali ulashishingiz yoki qo'lda yozishingiz mumkin):",
            reply_markup=PHONE_MENU,
        )
        return

    await message.answer(
        "Assalomu alaykum! Xizmat ko'rsatish botiga xush kelibsiz.\n\n"
        "Bu yerda siz texnik va xo'jalik xizmatlari bo'yicha murojaat qoldirishingiz mumkin.",
        reply_markup=MAIN_MENU,
    )


@dp.message(Command("bekor"))
@dp.message(F.text == CANCEL_BTN)
async def cancel_any(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Bekor qiladigan narsa yo'q. Bosh menyu:", reply_markup=MAIN_MENU)
        return
    await state.clear()
    await message.answer("Bekor qilindi. Bosh menyu:", reply_markup=MAIN_MENU)


@dp.message(OnboardingFSM.entering_phone, F.contact)
async def receive_phone_contact(message: Message, state: FSMContext):
    await api_client.upsert_customer(
        telegram_id=str(message.from_user.id), phone=message.contact.phone_number
    )
    await state.clear()
    await message.answer(
        "Rahmat! Endi murojaat qoldirishingiz mumkin.",
        reply_markup=MAIN_MENU,
    )


@dp.message(OnboardingFSM.entering_phone)
async def receive_phone_text(message: Message, state: FSMContext):
    await api_client.upsert_customer(
        telegram_id=str(message.from_user.id), phone=message.text.strip()
    )
    await state.clear()
    await message.answer(
        "Rahmat! Endi murojaat qoldirishingiz mumkin.",
        reply_markup=MAIN_MENU,
    )


async def _prompt_category(message: Message, state: FSMContext):
    status, cats = await api_client.list_categories()
    if status != 200 or not cats:
        await message.answer("Kategoriyalarni yuklashda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.")
        return

    await state.update_data(categories={str(c["id"]): c["name"] for c in cats})
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=c["name"])] for c in cats] + [[KeyboardButton(text=CANCEL_BTN)]],
        resize_keyboard=True,
    )
    await state.set_state(NewRequestFSM.choosing_category)
    await message.answer("Xizmat turini tanlang:", reply_markup=kb)


@dp.message(F.text == "🆕 Yangi murojaat")
async def new_request_start(message: Message, state: FSMContext):
    status, buildings = await api_client.list_buildings()
    if status != 200:
        await message.answer("Binolar ro'yxatini yuklashda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.")
        return

    if not buildings:
        # Tizimda hali binolar ro'yxatga kiritilmagan — bu murojaat qoldirishga
        # to'sqinlik qilmasligi kerak, shuning uchun bino tanlash bosqichini
        # o'tkazib yuborib, to'g'ridan-to'g'ri xizmat turini so'raymiz.
        await state.update_data(buildings={})
        await _prompt_category(message, state)
        return

    await state.update_data(buildings={str(b["id"]): b["name"] for b in buildings})
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b["name"])] for b in buildings] + [[KeyboardButton(text=CANCEL_BTN)]],
        resize_keyboard=True,
    )
    await state.set_state(NewRequestFSM.choosing_building)
    await message.answer("Qaysi binoda muammo bor?", reply_markup=kb)


@dp.message(NewRequestFSM.choosing_building)
async def choose_building(message: Message, state: FSMContext):
    data = await state.get_data()
    buildings = data.get("buildings", {})
    building_id = next((bid for bid, name in buildings.items() if name == message.text), None)

    if not building_id:
        await message.answer("Iltimos, ro'yxatdan binoni tanlang.")
        return

    await state.update_data(building_id=building_id, building_name=message.text)
    await _prompt_category(message, state)


@dp.message(NewRequestFSM.choosing_category)
async def choose_category(message: Message, state: FSMContext):
    data = await state.get_data()
    categories = data.get("categories", {})
    category_id = next((cid for cid, name in categories.items() if name == message.text), None)

    if not category_id:
        await message.answer("Iltimos, ro'yxatdan xizmat turini tanlang.")
        return

    await state.update_data(category_id=category_id, category_name=message.text)
    await state.set_state(NewRequestFSM.entering_comment)
    await message.answer(
        "Muammoni batafsil tasvirlab bering (matn ko'rinishida):\n\n"
        "Bekor qilish uchun /bekor yozing.",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(NewRequestFSM.entering_comment)
async def enter_comment(message: Message, state: FSMContext):
    await state.update_data(description=message.text, photos=[], videos=[])
    await state.set_state(NewRequestFSM.uploading_photo)
    await message.answer("Fotosurat biriktirmoqchimisiz? (ixtiyoriy)", reply_markup=SKIP_MENU)


@dp.message(NewRequestFSM.uploading_photo, F.photo)
async def upload_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append({"file_type": "photo", "file_ref": message.photo[-1].file_id})
    await state.update_data(photos=photos)
    await message.answer("Fotosurat qabul qilindi. Yana biriktirasizmi, yoki davom etamizmi?",
                          reply_markup=SKIP_MENU)


@dp.message(NewRequestFSM.uploading_photo)
async def skip_photo(message: Message, state: FSMContext):
    await state.set_state(NewRequestFSM.uploading_video)
    await message.answer("Video biriktirmoqchimisiz? (ixtiyoriy)", reply_markup=SKIP_MENU)


@dp.message(NewRequestFSM.uploading_video, F.video)
async def upload_video(message: Message, state: FSMContext):
    data = await state.get_data()
    videos = data.get("videos", [])
    videos.append({"file_type": "video", "file_ref": message.video.file_id})
    await state.update_data(videos=videos)
    await state.set_state(NewRequestFSM.entering_org_unit)
    await message.answer(
        "Departament, Boshqarma (yoki Mustaqil boshqarma), xona va qavatingizni birga yozing "
        "(masalan: «Moliya departamenti, Hisob-kitob boshqarmasi, 215-xona, 2-qavat»):\n\n"
        "Bekor qilish uchun /bekor yozing.",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(NewRequestFSM.uploading_video)
async def skip_video(message: Message, state: FSMContext):
    await state.set_state(NewRequestFSM.entering_org_unit)
    await message.answer(
        "Departament, Boshqarma (yoki Mustaqil boshqarma), xona va qavatingizni birga yozing "
        "(masalan: «Moliya departamenti, Hisob-kitob boshqarmasi, 215-xona, 2-qavat»):\n\n"
        "Bekor qilish uchun /bekor yozing."
    )


@dp.message(NewRequestFSM.entering_org_unit)
async def enter_org_unit(message: Message, state: FSMContext):
    is_independent = "mustaqil" in message.text.lower()
    await state.update_data(org_division=message.text, org_is_independent=is_independent)
    await _finalize_request(message, state)


async def _finalize_request(message: Message, state: FSMContext):
    data = await state.get_data()
    attachments = data.get("photos", []) + data.get("videos", [])

    status, result = await api_client.create_request(
        telegram_id=str(message.from_user.id),
        category_id=int(data["category_id"]),
        description=data["description"],
        org_department=data.get("org_department"),
        org_division=data.get("org_division"),
        org_is_independent=data.get("org_is_independent", False),
        room_number=data.get("room_number"),
        attachments=attachments,
        building_id=int(data["building_id"]) if data.get("building_id") else None,
    )

    await state.clear()
    if status == 200:
        await message.answer(
            f"✅ Murojaatingiz qabul qilindi!\nMurojaat raqami: {result['number']}\n\n"
            "Holatini «📋 Mening murojaatlarim» bo'limidan kuzatishingiz mumkin.",
            reply_markup=MAIN_MENU,
        )
    else:
        await message.answer("Xatolik yuz berdi. Iltimos qayta urinib ko'ring.", reply_markup=MAIN_MENU)


@dp.message(F.text == "📋 Mening murojaatlarim")
async def my_requests(message: Message):
    status, reqs = await api_client.list_customer_requests(str(message.from_user.id))
    if status != 200 or not reqs:
        await message.answer("Sizda hali murojaatlar yo'q.")
        return

    lines = []
    for r in reqs:
        label = STATUS_LABELS.get(r["status"], r["status"])
        overdue = " ⚠️ MUDDATI O'TDI" if r["is_overdue"] else ""
        line = f"№{r['number']} — {r['category']}\nHolat: {label}{overdue}"
        if r.get("executor_name"):
            phone_part = f" ({r['executor_phone']})" if r.get("executor_phone") else ""
            line += f"\nMas'ul mutaxassis: {r['executor_name']}{phone_part}"
        lines.append(line + "\n")
    await message.answer("\n".join(lines))

    done_reqs = [r for r in reqs if r["status"] in ("bajarildi", "yopildi")]
    unrated = []
    for r in done_reqs:
        detail_status, detail = await api_client.get_request(r["id"])
        # rating mavjudligini bilish uchun to'liq ma'lumot kerak emas — shunchaki takliflaymiz
        unrated.append(r)
    if unrated:
        await message.answer(
            "Bajarilgan murojaatni baholash uchun uning raqamini yuboring (masalan REQ-2026-000001).")


@dp.callback_query(F.data.startswith("rate:"))
async def handle_rate_callback(callback: CallbackQuery, state: FSMContext):
    _, req_id, stars = callback.data.split(":")
    await state.update_data(request_id=int(req_id), stars=int(stars))
    await state.set_state(RatingFSM.entering_feedback)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer(f"Siz {stars} ta yulduz qo'ydingiz.")
    await callback.message.answer(
        "Rahmat! Qo'shimcha fikringiz bo'lsa yozing (yoki «-» deb yuboring):"
    )


@dp.message(F.text.startswith("REQ-"))
async def start_rating(message: Message, state: FSMContext):
    status, reqs = await api_client.list_customer_requests(str(message.from_user.id))
    match = next((r for r in reqs if r["number"] == message.text.strip()), None)
    if not match:
        await message.answer("Bunday raqamli murojaat topilmadi.")
        return
    if match["status"] not in ("bajarildi", "yopildi"):
        await message.answer("Bu murojaat hali bajarilmagan, baholab bo'lmaydi.")
        return
    await state.update_data(request_id=match["id"])
    await state.set_state(RatingFSM.choosing_stars)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⭐" * i)] for i in range(5, 0, -1)],
        resize_keyboard=True,
    )
    await message.answer("Xizmat sifatini baholang:", reply_markup=kb)


@dp.message(RatingFSM.choosing_stars)
async def choose_stars(message: Message, state: FSMContext):
    stars = message.text.count("⭐")
    if not (1 <= stars <= 5):
        await message.answer("Iltimos, ⭐ tugmalaridan birini tanlang.")
        return
    await state.update_data(stars=stars)
    await state.set_state(RatingFSM.entering_feedback)
    await message.answer("Qo'shimcha fikringiz bo'lsa yozing (yoki «-» deb yuboring):",
                          reply_markup=ReplyKeyboardRemove())


@dp.message(RatingFSM.entering_feedback)
async def enter_feedback(message: Message, state: FSMContext):
    comment = None if message.text.strip() == "-" else message.text
    await state.update_data(comment=comment)
    await state.set_state(RatingFSM.entering_suggestion)
    await message.answer(
        "Xizmat sifatini yaxshilash bo'yicha taklif yoki so'rovingiz bo'lsa yozing (yoki «-» deb yuboring):"
    )


@dp.message(RatingFSM.entering_suggestion)
async def enter_suggestion(message: Message, state: FSMContext):
    data = await state.get_data()
    suggestion = None if message.text.strip() == "-" else message.text
    await api_client.rate_request(data["request_id"], data["stars"], data.get("comment"), suggestion)
    await state.clear()
    await message.answer("Rahmat! Fikr-mulohazangiz uchun tashakkur.", reply_markup=MAIN_MENU)


@dp.message(F.text == "ℹ️ Yordam")
async def help_handler(message: Message):
    await message.answer(
        "Bu bot orqali siz:\n"
        "• Texnik/xo'jalik xizmatlari bo'yicha murojaat qoldirishingiz\n"
        "• Murojaat holatini (Jarayonda, Bajarildi, Rad etildi va h.k.) kuzatishingiz\n"
        "• Bajarilgan xizmatni 5 yulduzgacha baholashingiz mumkin.\n\n"
        "Savollar bo'yicha: +998 99 978 87 80"
    )


async def main():
    if not BOT_TOKEN:
        logger.error("CUSTOMER_BOT_TOKEN sozlanmagan!")
        return
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
