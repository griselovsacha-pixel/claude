from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, Contact
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from keyboards.keyboards import main_menu_kb, my_bookings_kb, booking_detail_kb, share_phone_kb, rating_kb
from utils.helpers import format_booking
from config import ADMIN_IDS

router = Router()


class ProfileFSM(StatesGroup):
    waiting_phone = State()
    waiting_review_text = State()


# ─────────────────────────────────────────────
#  ПРОФИЛЬ
# ─────────────────────────────────────────────
@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: Message):
    user_row = await db.get_user(message.from_user.id)
    if not user_row:
        await message.answer("Профиль не найден. Нажмите /start")
        return

    bookings = await db.get_user_bookings(message.from_user.id)
    done = [b for b in bookings if b["status"] == "done"]
    total_spent = sum(b["price"] for b in done)
    upcoming = [b for b in bookings if b["status"] in ("pending", "confirmed")]

    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"📛 <b>Имя:</b> {user_row['full_name']}\n"
        f"📱 <b>Телефон:</b> {user_row['phone'] or '—'}\n"
        f"📅 <b>Записей:</b> {len(bookings)} всего\n"
        f"✅ <b>Выполнено:</b> {len(done)} визитов\n"
        f"⏳ <b>Предстоящих:</b> {len(upcoming)}\n"
        f"💰 <b>Потрачено:</b> {total_spent}₽\n"
    )

    # Статус клиента
    if len(done) >= 10:
        text += "\n🏆 <b>Статус:</b> VIP-клиент"
    elif len(done) >= 5:
        text += "\n⭐ <b>Статус:</b> Постоянный клиент"
    elif len(done) >= 1:
        text += "\n💅 <b>Статус:</b> Клиент"
    else:
        text += "\n🌱 <b>Статус:</b> Новый клиент"

    if not user_row["phone"]:
        text += "\n\n💡 <i>Добавьте номер телефона — мастер сможет с вами связаться!</i>"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    if not user_row["phone"]:
        builder.button(text="📱 Добавить телефон", callback_data="add_phone")
    builder.button(text="📋 История записей", callback_data="my_bookings_history")
    builder.adjust(1)

    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "add_phone")
async def request_phone(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📱 Поделитесь номером телефона или введите его вручную\n"
        "Формат: +79991234567",
        reply_markup=share_phone_kb()
    )
    await state.set_state(ProfileFSM.waiting_phone)
    await callback.answer()


@router.message(ProfileFSM.waiting_phone, F.contact)
async def save_phone_from_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await db.set_user_phone(message.from_user.id, phone)
    user = await db.get_user(message.from_user.id)
    is_admin = message.from_user.id in ADMIN_IDS or (user and user["is_admin"])
    await state.clear()
    await message.answer(f"✅ Телефон {phone} сохранён!", reply_markup=main_menu_kb(is_admin))


@router.message(ProfileFSM.waiting_phone)
async def save_phone_manual(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+") or len(phone) < 10:
        await message.answer("❌ Неверный формат. Введите номер в формате +79991234567")
        return
    await db.set_user_phone(message.from_user.id, phone)
    user = await db.get_user(message.from_user.id)
    is_admin = message.from_user.id in ADMIN_IDS or (user and user["is_admin"])
    await state.clear()
    await message.answer(f"✅ Телефон {phone} сохранён!", reply_markup=main_menu_kb(is_admin))


# ─────────────────────────────────────────────
#  МОИ ЗАПИСИ
# ─────────────────────────────────────────────
@router.message(F.text == "🗒 Мои записи")
@router.callback_query(F.data == "my_bookings")
async def show_my_bookings(event, state: FSMContext = None):
    if isinstance(event, CallbackQuery):
        tg_id = event.from_user.id
        send = event.message.edit_text
        answer = event.answer
    else:
        tg_id = event.from_user.id
        send = event.answer
        answer = None

    bookings = await db.get_user_bookings(tg_id, upcoming_only=True)
    if not bookings:
        text = (
            "🗒 <b>Ваши предстоящие записи</b>\n\n"
            "У вас нет активных записей.\n"
            "Запишитесь на удобное время! 💅"
        )
        await send(text)
        if answer:
            await answer()
        return

    await send(
        f"🗒 <b>Ваши предстоящие записи</b> ({len(bookings)} шт.)\n\nНажмите на запись для подробностей:",
        reply_markup=my_bookings_kb(bookings)
    )
    if answer:
        await answer()


@router.callback_query(F.data == "my_bookings_history")
async def show_bookings_history(callback: CallbackQuery):
    bookings = await db.get_user_bookings(callback.from_user.id, upcoming_only=False)
    if not bookings:
        await callback.message.edit_text("История записей пуста.")
        await callback.answer()
        return
    await callback.message.edit_text(
        f"📋 <b>История записей</b> ({len(bookings)} шт.):",
        reply_markup=my_bookings_kb(bookings[:15])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_bk:"))
async def view_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    booking = await db.get_booking(booking_id)
    if not booking or booking["tg_id"] != callback.from_user.id:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    has_rev = await db.has_review(booking_id)
    text = f"📋 <b>Запись #{booking_id}</b>\n\n{format_booking(booking)}"
    await callback.message.edit_text(
        text,
        reply_markup=booking_detail_kb(booking_id, booking["status"], has_rev)
    )
    await callback.answer()


# ─────────────────────────────────────────────
#  ОТЗЫВ
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("review:"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.split(":")[1])
    await state.update_data(review_booking_id=booking_id)
    await callback.message.edit_text(
        "⭐ <b>Оставьте отзыв</b>\n\nКак вы оцениваете визит?",
        reply_markup=rating_kb(booking_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rate:"))
async def choose_rating(callback: CallbackQuery, state: FSMContext):
    _, booking_id_str, rating_str = callback.data.split(":")
    booking_id = int(booking_id_str)
    rating = int(rating_str)
    await state.update_data(rating=rating, review_booking_id=booking_id)

    stars_str = "⭐" * rating
    await callback.message.edit_text(
        f"Вы поставили: {stars_str}\n\n"
        "💬 Напишите комментарий к отзыву (или отправьте /skip):"
    )
    await state.set_state(ProfileFSM.waiting_review_text)
    await callback.answer()


@router.message(ProfileFSM.waiting_review_text)
async def save_review(message: Message, state: FSMContext):
    data = await state.get_data()
    text = None if message.text.strip() == "/skip" else message.text[:1000]

    user = await db.get_user(message.from_user.id)
    await db.add_review(
        user_id_db=user["id"],
        booking_id=data["review_booking_id"],
        rating=data["rating"],
        text=text
    )
    await state.clear()
    stars_str = "⭐" * data["rating"]
    await message.answer(
        f"✅ <b>Спасибо за отзыв!</b>\n\n"
        f"Оценка: {stars_str}\n"
        f"{'Комментарий: «' + text + '»' if text else ''}\n\n"
        "Ваш отзыв поможет нам стать лучше! 💕"
    )
