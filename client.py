from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import SALON_NAME, SALON_ADDRESS, SALON_PHONE, SALON_WORK_HOURS, SALON_INSTAGRAM, ADMIN_IDS
from database import db
from keyboards.keyboards import main_menu_kb, categories_kb, services_kb, masters_kb, master_info_kb
from utils.helpers import stars, format_date_ru

router = Router()


# ─────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    await db.upsert_user(user.id, user.username or "", user.full_name)

    db_user = await db.get_user(user.id)
    is_admin = user.id in ADMIN_IDS or (db_user and db_user["is_admin"])

    text = (
        f"👋 Добро пожаловать в <b>{SALON_NAME}</b>!\n\n"
        f"Мы рады видеть вас, <b>{user.first_name}</b>! 💅\n\n"
        f"📍 {SALON_ADDRESS}\n"
        f"📞 {SALON_PHONE}\n"
        f"🕐 {SALON_WORK_HOURS}\n"
        f"📸 {SALON_INSTAGRAM}\n\n"
        "Выберите нужный раздел:"
    )
    await message.answer(text, reply_markup=main_menu_kb(is_admin))


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📋 <b>Как пользоваться ботом:</b>\n\n"
        "📅 <b>Записаться</b> — выберите услугу, мастера, дату и время\n"
        "🗒 <b>Мои записи</b> — просмотр и отмена записей\n"
        "💰 <b>Услуги и цены</b> — полный прайс-лист\n"
        "👩‍🎨 <b>Наши мастера</b> — знакомство с командой\n"
        "⭐ <b>Отзывы</b> — мнения клиентов\n"
        "👤 <b>Мой профиль</b> — личные данные\n\n"
        f"По вопросам: {SALON_PHONE}"
    )
    await message.answer(text)


# ─────────────────────────────────────────────
#  УСЛУГИ И ЦЕНЫ
# ─────────────────────────────────────────────
@router.message(F.text == "💰 Услуги и цены")
async def show_price_list(message: Message):
    services = await db.get_services()
    if not services:
        await message.answer("Услуги временно недоступны.")
        return

    # Группируем по категориям
    categories: dict = {}
    for s in services:
        categories.setdefault(s["category"], []).append(s)

    cat_icons = {
        "Маникюр": "💅", "Наращивание": "✨", "Педикюр": "🦶",
        "Дизайн": "🎨", "Уход": "🌿", "Прочее": "📌"
    }
    text = "💰 <b>Прайс-лист</b>\n\n"
    for cat, items in categories.items():
        icon = cat_icons.get(cat, "▪️")
        text += f"{icon} <b>{cat}</b>\n"
        for s in items:
            text += f"  • {s['name']} — <b>{s['price']}₽</b> ({s['duration']} мин)\n"
        text += "\n"
    text += "Нажмите <b>«Записаться»</b> чтобы забронировать время!"
    await message.answer(text)


# ─────────────────────────────────────────────
#  НАШИ МАСТЕРА
# ─────────────────────────────────────────────
@router.message(F.text == "👩‍🎨 Наши мастера")
async def show_masters(message: Message):
    masters = await db.get_masters()
    if not masters:
        await message.answer("Информация о мастерах временно недоступна.")
        return
    await message.answer(
        "👩‍🎨 <b>Наши мастера</b>\n\nВыберите мастера для подробной информации:",
        reply_markup=masters_kb(masters)
    )


@router.callback_query(F.data.startswith("mst:"))
async def show_master_detail(callback: CallbackQuery):
    master_id = int(callback.data.split(":")[1])
    master = await db.get_master(master_id)
    if not master:
        await callback.answer("Мастер не найден", show_alert=True)
        return

    rating_row = await db.get_master_rating(master_id)
    avg = rating_row["avg_rating"] or 0
    total = rating_row["total"] or 0

    text = (
        f"👩 <b>{master['name']}</b>\n"
        f"✂️ <i>{master['specialty']}</i>\n\n"
        f"{master['bio'] or ''}\n\n"
    )
    if total > 0:
        text += f"⭐ Рейтинг: {stars(avg)} ({avg:.1f} — {total} отзывов)\n"
    else:
        text += "⭐ Рейтингов пока нет\n"

    if master["photo_id"]:
        await callback.message.answer_photo(
            photo=master["photo_id"],
            caption=text,
            reply_markup=master_info_kb(master_id)
        )
    else:
        await callback.message.edit_text(text, reply_markup=master_info_kb(master_id))
    await callback.answer()


@router.callback_query(F.data == "back:masters_list")
async def back_to_masters(callback: CallbackQuery):
    masters = await db.get_masters()
    await callback.message.edit_text(
        "👩‍🎨 <b>Наши мастера</b>\n\nВыберите мастера:",
        reply_markup=masters_kb(masters)
    )
    await callback.answer()


# ─────────────────────────────────────────────
#  ОТЗЫВЫ
# ─────────────────────────────────────────────
@router.message(F.text == "⭐ Отзывы")
async def show_reviews(message: Message):
    reviews = await db.get_reviews(limit=10)
    if not reviews:
        await message.answer(
            "⭐ <b>Отзывы</b>\n\n"
            "Пока отзывов нет. Будьте первым! 😊\n"
            "После посещения вы сможете оставить отзыв в разделе «Мои записи»."
        )
        return

    text = "⭐ <b>Последние отзывы</b>\n\n"
    for r in reviews:
        text += (
            f"{stars(r['rating'])} <b>{r['full_name']}</b>\n"
            f"💅 {r['service_name']} | 👩 {r['master_name']}\n"
        )
        if r["text"]:
            text += f"<i>«{r['text']}»</i>\n"
        text += f"<code>{r['created_at'][:10]}</code>\n\n"
    await message.answer(text)
