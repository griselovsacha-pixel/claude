from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from keyboards.keyboards import (
    categories_kb, services_kb, masters_kb, dates_kb, times_kb,
    confirm_booking_kb, main_menu_kb, cancel_kb
)
from utils.helpers import get_available_slots, format_booking, format_date_ru
from config import ADMIN_IDS

router = Router()


class BookingFSM(StatesGroup):
    choose_category = State()
    choose_service  = State()
    choose_master   = State()
    choose_date     = State()
    choose_time     = State()
    add_comment     = State()
    confirm         = State()


# ─────────────────────────────────────────────
#  START BOOKING
# ─────────────────────────────────────────────
async def start_booking(target, state: FSMContext, master_id: int = None):
    """Универсальный старт: из меню или после выбора мастера."""
    await state.clear()
    categories = await db.get_service_categories()
    text = "📅 <b>Запись на маникюр</b>\n\nШаг 1️⃣: Выберите категорию услуг:"
    kb = categories_kb(categories)
    if hasattr(target, "message"):
        await target.message.answer(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)

    await state.set_state(BookingFSM.choose_category)
    if master_id:
        await state.update_data(preset_master=master_id)


@router.message(F.text == "📅 Записаться")
async def book_from_menu(message: Message, state: FSMContext):
    await start_booking(message, state)


@router.callback_query(F.data.startswith("book_master:"))
async def book_specific_master(callback: CallbackQuery, state: FSMContext):
    master_id = int(callback.data.split(":")[1])
    await start_booking(callback, state, master_id=master_id)


# ─────────────────────────────────────────────
#  КАТЕГОРИЯ → УСЛУГА
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("cat:"), BookingFSM.choose_category)
async def choose_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":", 1)[1]
    await state.update_data(category=category)
    services = await db.get_services(category)
    await callback.message.edit_text(
        f"Шаг 1️⃣: <b>{category}</b>\n\nШаг 2️⃣: Выберите услугу:",
        reply_markup=services_kb(services)
    )
    await state.set_state(BookingFSM.choose_service)
    await callback.answer()


@router.callback_query(F.data == "back:categories", BookingFSM.choose_service)
async def back_to_categories(callback: CallbackQuery, state: FSMContext):
    categories = await db.get_service_categories()
    await callback.message.edit_text(
        "Шаг 1️⃣: Выберите категорию услуг:",
        reply_markup=categories_kb(categories)
    )
    await state.set_state(BookingFSM.choose_category)
    await callback.answer()


# ─────────────────────────────────────────────
#  УСЛУГА → МАСТЕР
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("srv:"), BookingFSM.choose_service)
async def choose_service(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split(":")[1])
    service = await db.get_service(service_id)
    await state.update_data(service_id=service_id, service_name=service["name"],
                             service_duration=service["duration"], service_price=service["price"])

    data = await state.get_data()
    preset_master = data.get("preset_master")

    if preset_master:
        master = await db.get_master(preset_master)
        await state.update_data(master_id=preset_master, master_name=master["name"])
        await callback.message.edit_text(
            f"✅ Услуга: <b>{service['name']}</b>\n"
            f"✅ Мастер: <b>{master['name']}</b>\n\n"
            "Шаг 3️⃣: Выберите дату:",
            reply_markup=dates_kb()
        )
        await state.set_state(BookingFSM.choose_date)
    else:
        masters = await db.get_masters()
        await callback.message.edit_text(
            f"✅ Услуга: <b>{service['name']}</b> — {service['price']}₽\n\n"
            "Шаг 3️⃣: Выберите мастера:",
            reply_markup=masters_kb(masters)
        )
        await state.set_state(BookingFSM.choose_master)
    await callback.answer()


@router.callback_query(F.data == "back:services", BookingFSM.choose_master)
async def back_to_services(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    services = await db.get_services(data.get("category"))
    await callback.message.edit_text(
        "Шаг 2️⃣: Выберите услугу:",
        reply_markup=services_kb(services)
    )
    await state.set_state(BookingFSM.choose_service)
    await callback.answer()


# ─────────────────────────────────────────────
#  МАСТЕР → ДАТА
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("mst:"), BookingFSM.choose_master)
async def choose_master(callback: CallbackQuery, state: FSMContext):
    master_id = int(callback.data.split(":")[1])
    master = await db.get_master(master_id)
    await state.update_data(master_id=master_id, master_name=master["name"])
    data = await state.get_data()
    await callback.message.edit_text(
        f"✅ Услуга: <b>{data['service_name']}</b>\n"
        f"✅ Мастер: <b>{master['name']}</b>\n\n"
        "Шаг 4️⃣: Выберите дату:",
        reply_markup=dates_kb()
    )
    await state.set_state(BookingFSM.choose_date)
    await callback.answer()


# ─────────────────────────────────────────────
#  ДАТА → ВРЕМЯ
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("date:"), BookingFSM.choose_date)
async def choose_date(callback: CallbackQuery, state: FSMContext):
    booking_date = callback.data.split(":")[1]
    data = await state.get_data()
    await state.update_data(booking_date=booking_date)

    booked = await db.get_master_bookings(data["master_id"], booking_date)
    available = get_available_slots(booked, data["service_duration"], booking_date)

    if not available:
        await callback.answer("😔 На этот день нет свободных окон, выберите другую дату.", show_alert=True)
        return

    date_str = format_date_ru(booking_date)
    await callback.message.edit_text(
        f"✅ Услуга: <b>{data['service_name']}</b>\n"
        f"✅ Мастер: <b>{data['master_name']}</b>\n"
        f"✅ Дата: <b>{date_str}</b>\n\n"
        f"Шаг 5️⃣: Выберите время (свободно {len(available)} окон):",
        reply_markup=times_kb(available, booking_date)
    )
    await state.set_state(BookingFSM.choose_time)
    await callback.answer()


@router.callback_query(F.data == "back:dates", BookingFSM.choose_time)
async def back_to_dates(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Шаг 4️⃣: Выберите дату:",
        reply_markup=dates_kb()
    )
    await state.set_state(BookingFSM.choose_date)
    await callback.answer()


# ─────────────────────────────────────────────
#  ВРЕМЯ → КОММЕНТАРИЙ
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("time:"), BookingFSM.choose_time)
async def choose_time(callback: CallbackQuery, state: FSMContext):
    booking_time = callback.data.split(":")[1]
    await state.update_data(booking_time=booking_time)
    data = await state.get_data()

    await callback.message.edit_text(
        f"✅ Услуга: <b>{data['service_name']}</b>\n"
        f"✅ Мастер: <b>{data['master_name']}</b>\n"
        f"✅ Дата: <b>{format_date_ru(data['booking_date'])}</b>\n"
        f"✅ Время: <b>{booking_time}</b>\n\n"
        "💬 Хотите добавить комментарий?\n"
        "<i>Например: «первый раз, хочу натуральный дизайн», «есть аллергия на...»</i>\n\n"
        "Напишите комментарий или нажмите /skip чтобы пропустить:",
        reply_markup=cancel_kb()
    )
    await state.set_state(BookingFSM.add_comment)
    await callback.answer()


@router.message(BookingFSM.add_comment, F.text == "/skip")
@router.message(BookingFSM.add_comment, F.text.startswith("/skip"))
async def skip_comment(message: Message, state: FSMContext):
    await state.update_data(comment=None)
    await _show_confirmation(message, state)


@router.message(BookingFSM.add_comment)
async def add_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text[:500])
    await _show_confirmation(message, state)


async def _show_confirmation(target: Message, state: FSMContext):
    data = await state.get_data()
    text = (
        "📋 <b>Проверьте данные записи:</b>\n\n"
        f"💅 <b>Услуга:</b> {data['service_name']}\n"
        f"👩 <b>Мастер:</b> {data['master_name']}\n"
        f"📅 <b>Дата:</b> {format_date_ru(data['booking_date'])}\n"
        f"⏰ <b>Время:</b> {data['booking_time']}\n"
        f"💰 <b>Стоимость:</b> {data['service_price']}₽\n"
    )
    if data.get("comment"):
        text += f"💬 <b>Комментарий:</b> {data['comment']}\n"
    text += "\n<b>Всё верно?</b>"

    # Создаём предварительную запись
    user = await db.get_user(target.from_user.id)
    booking_id = await db.create_booking(
        user_id=user["id"],
        master_id=data["master_id"],
        service_id=data["service_id"],
        booking_date=data["booking_date"],
        booking_time=data["booking_time"],
        comment=data.get("comment")
    )
    await state.update_data(booking_id=booking_id)
    await state.set_state(BookingFSM.confirm)

    await target.answer(text, reply_markup=confirm_booking_kb(booking_id))


# ─────────────────────────────────────────────
#  ПОДТВЕРЖДЕНИЕ / ОТМЕНА
# ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("confirm_bk:"))
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.split(":")[1])
    booking = await db.get_booking(booking_id)

    # Последняя проверка доступности
    ok = await db.is_slot_available(
        booking["master_id"], booking["booking_date"],
        booking["booking_time"], booking["duration"]
    )
    # Если сама запись уже существует, слот будет занят собой — это нормально
    # Обновляем статус на pending (запись уже создана)
    await db.update_booking_status(booking_id, "pending")

    user = await db.get_user(callback.from_user.id)
    is_admin = callback.from_user.id in ADMIN_IDS or user["is_admin"]

    await callback.message.edit_text(
        f"🎉 <b>Запись оформлена!</b>\n\n"
        f"{format_booking(booking, show_status=True)}\n\n"
        "Мастер скоро подтвердит вашу запись.\n"
        "Мы напомним вам за 24 часа и за 2 часа до визита! 🔔"
    )
    await state.clear()

    # Уведомляем администраторов
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    bot = callback.bot
    notif_text = (
        f"🆕 <b>Новая запись #{booking_id}</b>\n\n"
        f"👤 Клиент: {booking['client_name']}\n"
        f"📞 Телефон: {booking['client_phone'] or 'не указан'}\n"
        f"{format_booking(booking, show_status=False)}"
    )
    from keyboards.keyboards import admin_booking_kb
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, notif_text,
                                    reply_markup=admin_booking_kb(booking_id, "pending"))
        except Exception:
            pass

    await callback.answer("✅ Запись создана!")


@router.callback_query(F.data == "cancel_booking")
async def cancel_new_booking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if bid := data.get("booking_id"):
        await db.cancel_booking(bid)
    await state.clear()
    await callback.message.edit_text("❌ Запись отменена. Возвращайтесь!")
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_bk:"))
async def cancel_existing_booking(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.split(":")[1])
    await db.cancel_booking(booking_id, tg_id=callback.from_user.id)
    await callback.message.edit_text(
        f"❌ Запись #{booking_id} отменена.\n\n"
        "Если хотите перенести — просто запишитесь снова. До встречи! 💅"
    )
    await callback.answer("Запись отменена")
