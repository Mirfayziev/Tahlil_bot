"""
Telegram Bot №2 — Ijrochilar uchun (TZ p.15).
Har bir ijrochi faqat o'ziga tegishli topshiriqlarni ko'radi (Maxfiylik, p.15).

Ishga tushirish:
    python bots/executor_bot.py
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
    Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)

from bots.api_client import api_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("executor_bot")

BOT_TOKEN = os.environ.get("EXECUTOR_BOT_TOKEN", "")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

CANCEL_BTN = "❌ Bekor qilish"

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Yangi topshiriqlar")],
        [KeyboardButton(text="🛠 Jarayondagi ishlarim")],
    ],
    resize_keyboard=True,
)

CANCEL_MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=CANCEL_BTN)]], resize_keyboard=True
)


class ReportFSM(StatesGroup):
    entering_report = State()
    entering_time = State()
    uploading_files = State()


class RejectFSM(StatesGroup):
    entering_reason = State()


class InfoRequestFSM(StatesGroup):
    entering_question = State()


class ExtendFSM(StatesGroup):
    entering_hours = State()
    entering_reason = State()


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Assalomu alaykum! Ijrochilar uchun ishchi botga xush kelibsiz.\n"
        "Bu yerda sizga tayinlangan topshiriqlarni ko'rishingiz va bajarishingiz mumkin.",
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


def _format_task(t: dict) -> str:
    deadline = t.get("deadline_at", "")[:16].replace("T", " ") if t.get("deadline_at") else "-"
    return (
        f"№{t['number']} — {t['category']}\n"
        f"Bino: {t.get('building') or '-'}\n"
        f"Ustuvorlik: {t.get('priority', '-')}\n"
        f"Tavsif: {t['description']}\n"
        f"Bo'linma: {t.get('org_display') or t.get('address') or '-'}\n"
        f"Muddat: {deadline}\n"
        f"Holat: {t['status']}"
    )


@dp.message(F.text == "📥 Yangi topshiriqlar")
async def new_tasks(message: Message):
    status, tasks = await api_client.executor_tasks(str(message.from_user.id))
    if status != 200:
        await message.answer("Xatolik: siz tizimda ijrochi sifatida ro'yxatdan o'tmagansiz. "
                              "Administratorga murojaat qiling.")
        return

    pending = [t for t in tasks if t.get("response") is None]
    if not pending:
        await message.answer("Hozircha yangi topshiriqlar yo'q.")
        return

    for t in pending:
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=f"✅ Qabul qilish #{t['assignment_id']}")],
                [KeyboardButton(text=f"❌ Rad etish #{t['assignment_id']}")],
            ],
            resize_keyboard=True,
        )
        await message.answer(_format_task(t), reply_markup=kb)


@dp.message(F.text.startswith("✅ Qabul qilish"))
async def accept_task(message: Message):
    assignment_id = int(message.text.split("#")[-1])
    status, _ = await api_client.respond_assignment(assignment_id, "qabul_qilindi")
    if status == 200:
        await message.answer("Topshiriq qabul qilindi. Ish boshlanganda «Ish boshlash» tugmasidan foydalaning.",
                              reply_markup=MAIN_MENU)
        await start_working_prompt(message, assignment_id)
    else:
        await message.answer("Xatolik yuz berdi.")


@dp.message(F.text.startswith("❌ Rad etish"))
async def reject_task_start(message: Message, state: FSMContext):
    assignment_id = int(message.text.split("#")[-1])
    await state.update_data(assignment_id=assignment_id)
    await state.set_state(RejectFSM.entering_reason)
    await message.answer("Rad etish sababini yozing:", reply_markup=CANCEL_MENU)


@dp.message(RejectFSM.entering_reason)
async def reject_task_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    status, _ = await api_client.respond_assignment(data["assignment_id"], "rad_etildi", reason=message.text)
    await state.clear()
    if status == 200:
        await message.answer("Rad etildi. Ma'lumot dispetcherga yuborildi.", reply_markup=MAIN_MENU)
    else:
        await message.answer("Xatolik yuz berdi. Iltimos qayta urinib ko'ring.", reply_markup=MAIN_MENU)


async def start_working_prompt(message: Message, assignment_id: int):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"▶️ Ish boshlash #{assignment_id}")],
            [KeyboardButton(text=f"❓ Qo'shimcha ma'lumot so'rash #{assignment_id}")],
        ],
        resize_keyboard=True,
    )
    await message.answer("Davom etish uchun tanlang:", reply_markup=kb)


@dp.message(F.text.startswith("▶️ Ish boshlash"))
async def begin_work(message: Message):
    assignment_id = int(message.text.split("#")[-1])
    status, _ = await api_client.start_assignment(assignment_id)
    if status != 200:
        await message.answer("Xatolik yuz berdi. Iltimos qayta urinib ko'ring.")
        return
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=f"✔️ Bajarildi deb belgilash #{assignment_id}")],
            [KeyboardButton(text=f"⏱ Qo'shimcha vaqt so'rash #{assignment_id}")],
            [KeyboardButton(text=f"❓ Qo'shimcha ma'lumot so'rash #{assignment_id}")],
        ],
        resize_keyboard=True,
    )
    await message.answer("Ish boshlandi deb belgilandi. Muvaffaqiyatlar!", reply_markup=kb)


@dp.message(F.text.startswith("❓ Qo'shimcha ma'lumot so'rash"))
async def request_info_start(message: Message, state: FSMContext):
    assignment_id = int(message.text.split("#")[-1])
    await state.update_data(assignment_id=assignment_id)
    await state.set_state(InfoRequestFSM.entering_question)
    await message.answer("Mijozdan qanday qo'shimcha ma'lumot kerakligini yozing:",
                          reply_markup=CANCEL_MENU)


@dp.message(InfoRequestFSM.entering_question)
async def request_info_send(message: Message, state: FSMContext):
    data = await state.get_data()
    status, _ = await api_client.request_more_info(data["assignment_id"], message.text)
    await state.clear()
    if status == 200:
        await message.answer("So'rov mijozga yuborildi.", reply_markup=MAIN_MENU)
    else:
        await message.answer("Xatolik yuz berdi. Iltimos qayta urinib ko'ring.", reply_markup=MAIN_MENU)


@dp.message(F.text.startswith("⏱ Qo'shimcha vaqt so'rash"))
async def extend_start(message: Message, state: FSMContext):
    assignment_id = int(message.text.split("#")[-1])
    await state.update_data(assignment_id=assignment_id)
    await state.set_state(ExtendFSM.entering_hours)
    await message.answer("Necha soatga muddat uzaytirish kerak? (raqam kiriting)",
                          reply_markup=CANCEL_MENU)


@dp.message(ExtendFSM.entering_hours)
async def extend_hours(message: Message, state: FSMContext):
    try:
        hours = int(message.text.strip())
    except ValueError:
        await message.answer("Iltimos, faqat raqam kiriting.")
        return
    await state.update_data(hours=hours)
    await state.set_state(ExtendFSM.entering_reason)
    await message.answer("Sababini yozing:", reply_markup=CANCEL_MENU)


@dp.message(ExtendFSM.entering_reason)
async def extend_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    status, _ = await api_client.extend_assignment(data["assignment_id"], data["hours"], message.text)
    await state.clear()
    if status == 200:
        await message.answer("So'rov dispetcherga yuborildi, tasdiqlanishini kuting.", reply_markup=MAIN_MENU)
    else:
        await message.answer("Xatolik yuz berdi. Iltimos qayta urinib ko'ring.", reply_markup=MAIN_MENU)


@dp.message(F.text.startswith("✔️ Bajarildi deb belgilash"))
async def complete_start(message: Message, state: FSMContext):
    assignment_id = int(message.text.split("#")[-1])
    await state.update_data(assignment_id=assignment_id, files=[])
    await state.set_state(ReportFSM.entering_report)
    await message.answer("Bajarilgan ish haqida qisqacha hisobot yozing:", reply_markup=CANCEL_MENU)


@dp.message(ReportFSM.entering_report)
async def complete_report(message: Message, state: FSMContext):
    await state.update_data(report_text=message.text)
    await state.set_state(ReportFSM.entering_time)
    await message.answer("Ishga sarflangan vaqtni daqiqalarda kiriting (masalan 90):", reply_markup=CANCEL_MENU)


@dp.message(ReportFSM.entering_time)
async def complete_time(message: Message, state: FSMContext):
    try:
        minutes = int(message.text.strip())
    except ValueError:
        await message.answer("Iltimos, faqat raqam kiriting.")
        return
    await state.update_data(time_spent_minutes=minutes)
    await state.set_state(ReportFSM.uploading_files)
    skip_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Yakunlash")], [KeyboardButton(text=CANCEL_BTN)]],
        resize_keyboard=True,
    )
    await message.answer("Bajarilgan ish fotosuratini yuboring (ixtiyoriy), so'ng «✅ Yakunlash» tugmasini bosing.",
                          reply_markup=skip_kb)


@dp.message(ReportFSM.uploading_files, F.photo)
async def complete_upload_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    files = data.get("files", [])
    files.append({"file_type": "photo", "file_ref": message.photo[-1].file_id})
    await state.update_data(files=files)
    await message.answer("Qabul qilindi. Yana yuborishingiz mumkin yoki «✅ Yakunlash» tugmasini bosing.")


@dp.message(ReportFSM.uploading_files, F.document)
async def complete_upload_doc(message: Message, state: FSMContext):
    data = await state.get_data()
    files = data.get("files", [])
    files.append({"file_type": "file", "file_ref": message.document.file_id})
    await state.update_data(files=files)
    await message.answer("Fayl qabul qilindi. Davom etishingiz yoki yakunlashingiz mumkin.")


@dp.message(ReportFSM.uploading_files, F.text == "✅ Yakunlash")
async def complete_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    status, _ = await api_client.complete_assignment(
        data["assignment_id"], data["report_text"], data.get("time_spent_minutes"), data.get("files", [])
    )
    await state.clear()
    if status == 200:
        await message.answer("Ajoyib! Topshiriq bajarildi deb belgilandi. Rahmat!", reply_markup=MAIN_MENU)
    else:
        await message.answer("Xatolik yuz berdi. Iltimos qayta urinib ko'ring.", reply_markup=MAIN_MENU)


@dp.message(F.text == "🛠 Jarayondagi ishlarim")
async def my_active_tasks(message: Message):
    status, tasks = await api_client.executor_tasks(str(message.from_user.id))
    if status != 200 or not tasks:
        await message.answer("Sizda hozircha faol topshiriqlar yo'q.")
        return
    active = [t for t in tasks if t.get("response") == "qabul_qilindi"]
    if not active:
        await message.answer("Faol topshiriqlar topilmadi.")
        return
    for t in active:
        await message.answer(_format_task(t))


async def main():
    if not BOT_TOKEN:
        logger.error("EXECUTOR_BOT_TOKEN sozlanmagan!")
        return
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
