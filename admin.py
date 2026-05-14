from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date

from database import db
from keyboards.keyboards import admin_menu_kb, admin_booking_kb, main_menu_kb
from utils.helpers import format_booking, stars
from config import ADMIN_IDS

router = Router()


def is_admin(tg_id: int) -> bool:
    return tg_id in ADMIN_IDS


class AdminFSM(StatesGroup):
    waiting_date       = State()
    waiting_broadcast   = State()
    waiting_block_date  = State()
    waiting_block_time  = State()
    waiting_block_master = State()


# ─────────────────────────────────────────────
#  ADMIN GUARD
# ─────────────────────────────────────────────
@router.message(F.text == "🔧 Админ-панель")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 У вас нет доступа.")
        return
    await message.answer("🔧 <b>Панель администратора</b>", reply_markup=admin_menu_kb())


# ─────────────────────────────────────────────
#  СТАТИСТИКА
# ─────────────────────────────────────────────
@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    stats = await db.get_stats()
    popular = await db.get_popular_services(5)

    text = (
        "📊 <b>Статистика салона</b>\n\n"
        f"👥 Всего клиентов: <b>{stats['total_users']}</b>\n"
        f"📅 Всего записей: <b>{stats['total_bookings']}</b>\n"
        f"✅ Выполнено: <b>{stats['done_bookings']}</b>\n"
        f"❌ Отменено: <b>{stats['cancelled_bookings']}</b>\n"
        f"💰 Выручка: <b>{stats['total_revenue']}₽</b>\n"
        f"⭐ Средняя оценка: <b>{stars(stats['avg_rating'])} {stats['avg_rating']:.1f}</b>\n\n"
        "🏆 <b>Популярные услуги:</b>\n"
    )
    for i, p in enumerate(popular, 1):
        text += f"  {i}. {p['name']} — {p['cnt']} записей\n"

    await message.answer(text)


# ─────────────────────────────────────────────
#  ЗАПИСИ НА СЕГОДНЯ
# ─────────────────────────────────────────────
@router.message(F.text == "📋 Записи на сегодня")
async def bookings_today(message: Message):
    if not is_admin(message.from_user.id):
        return
    today = date.today().isoformat()
    bookings = await db.get_all_bookings_for_date(today)
    await _send_day_bookings(message, bookings, today)


async def _send_day_bookings(message: Message, bookings: list, day: str):
    if not bookings:
        await message.answer(f"📋 На <b>{day}</b> записей нет.")
        return
    text = f"📋 <b>Записи на {day}</b> ({len(bookings)} шт.)\n\n"
    for b in bookings:
        status_icon = {"pending":"⏳","confirmed":"✅","done":"🏁","cancelled":"❌"}.get(b["status"],"▪️")
        text += (
            f"{status_icon} <b>{b['booking_time']}</b> — {b['service_name']}\n"
            f"   👩 {b['master_name']} | 👤 {b['client_name']}\n"
            f"   📞 {b['client_phone'] or '—'} | 💰 {b['price']}₽\n\n"
        )
    await message.answer(text)


# ─────────────────────────────────────────────
#  ЗАПИСИ НА КОНКРЕТНУЮ ДАТУ
# ─────────────────────────────────────────────
@router.message(F.text == "📆 Записи на дату")
async def ask_date(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Введите дату в формате ГГГГ-ММ-ДД (например 2024-12-31):")
    await state.set_state(AdminFSM.waiting_date)


@router.message(AdminFSM.waiting_date)
async def show_date_bookings(message: Message, state: FSMContext):
    try:
        d = date.fromisoformat(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат даты. Попробуйте снова (ГГГГ-ММ-ДД):")
        return
    await state.clear()
    bookings = await db.get_all_bookings_for_date(d.isoformat())
    await _send_day_bookings(message, bookings, d.isoformat())


# ─────────────────────────────────────────────
#  ПОДТВЕРДИТЬ ЗАПИСЬ
# ─────────────────────────────────────────────
@router.message(F.text == "✅ Подтвердить запись")
async def ask_booking_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Введите ID записи для подтверждения:")
    await state.set_state(AdminFSM.waiting_date)  # reuse state for simplicity


@router.callback_query(F.data.startswith("adm_confirm:"))
async def admin_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    booking_id = int(callback.data.split(":")[1])
    await db.update_booking_status(booking_id, "confirmed")
    booking = await db.get_booking(booking_id)

    # Уведомляем клиента
    try:
        await callback.bot.send_message(
            booking["tg_id"],
            f"✅ <b>Ваша запись подтверждена!</b>\n\n{format_booking(booking)}\n\n"
            "Ждём вас! 💅"
        )
    except Exception:
        pass

    await callback.message.edit_text(
        f"✅ Запись #{booking_id} подтверждена!\nКлиент уведомлён.",
        reply_markup=admin_booking_kb(booking_id, "confirmed")
    )
    await callback.answer("Подтверждено!")


@router.callback_query(F.data.startswith("adm_done:"))
async def admin_done(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    booking_id = int(callback.data.split(":")[1])
    await db.update_booking_status(booking_id, "done")
    booking = await db.get_booking(booking_id)

    # Приглашаем оставить отзыв
    from keyboards.keyboards import rating_kb
    try:
        await callback.bot.send_message(
            booking["tg_id"],
            f"🏁 <b>Визит завершён!</b>\n\n"
            "Спасибо, что выбрали наш салон! 💕\n\n"
            "Пожалуйста, оцените качество услуги:",
            reply_markup=rating_kb(booking_id)
        )
    except Exception:
        pass

    await callback.message.edit_text(f"🏁 Запись #{booking_id} помечена как выполненная.")
    await callback.answer("Готово!")


@router.callback_query(F.data.startswith("adm_cancel:"))
async def admin_cancel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    booking_id = int(callback.data.split(":")[1])
    await db.cancel_booking(booking_id)
    booking = await db.get_booking(booking_id)

    try:
        await callback.bot.send_message(
            booking["tg_id"],
            f"❌ <b>Ваша запись отменена</b>\n\n{format_booking(booking)}\n\n"
            "Приносим извинения. Свяжитесь с нами для переноса."
        )
    except Exception:
        pass

    await callback.message.edit_text(f"❌ Запись #{booking_id} отменена.")
    await callback.answer("Отменено!")


# ─────────────────────────────────────────────
#  РАССЫЛКА
# ─────────────────────────────────────────────
@router.message(F.text == "📢 Рассылка")
async def ask_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "📢 <b>Рассылка</b>\n\nВведите текст сообщения для всех клиентов.\n"
        "Поддерживается HTML-разметка.\n\n/cancel — отмена"
    )
    await state.set_state(AdminFSM.waiting_broadcast)


@router.message(AdminFSM.waiting_broadcast, F.text == "/cancel")
async def cancel_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Рассылка отменена.", reply_markup=admin_menu_kb())


@router.message(AdminFSM.waiting_broadcast)
async def do_broadcast(message: Message, state: FSMContext):
    await state.clear()
    users = await db.get_all_users()
    text = f"📢 <b>Сообщение от салона:</b>\n\n{message.text}"
    sent = 0
    failed = 0
    for user in users:
        try:
            await message.bot.send_message(user["tg_id"], text)
            sent += 1
        except Exception:
            failed += 1
    await message.answer(
        f"📢 Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Не доставлено: {failed}",
        reply_markup=admin_menu_kb()
    )


# ─────────────────────────────────────────────
#  БЛОКИРОВКА СЛОТОВ
# ─────────────────────────────────────────────
@router.message(F.text == "🚫 Заблокировать слот")
async def ask_block(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    masters = await db.get_masters()
    text = "Выберите мастера (введите номер):\n\n"
    for i, m in enumerate(masters, 1):
        text += f"{i}. {m['name']}\n"
    await message.answer(text)
    await state.update_data(masters_list=[dict(m) for m in masters])
    await state.set_state(AdminFSM.waiting_block_master)


@router.message(AdminFSM.waiting_block_master)
async def block_choose_master(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        idx = int(message.text.strip()) - 1
        master = data["masters_list"][idx]
    except (ValueError, IndexError):
        await message.answer("❌ Неверный номер, попробуйте ещё раз:")
        return
    await state.update_data(block_master_id=master["id"], block_master_name=master["name"])
    await message.answer(
        f"Мастер: <b>{master['name']}</b>\n\n"
        "Введите дату блокировки (ГГГГ-ММ-ДД):"
    )
    await state.set_state(AdminFSM.waiting_block_date)


@router.message(AdminFSM.waiting_block_date)
async def block_choose_date(message: Message, state: FSMContext):
    try:
        d = date.fromisoformat(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат, введите ГГГГ-ММ-ДД:")
        return
    await state.update_data(block_date=d.isoformat())
    await message.answer(
        f"Дата: <b>{d.isoformat()}</b>\n\n"
        "Введите время (ЧЧ:ММ) или <b>all</b> чтобы заблокировать весь день:"
    )
    await state.set_state(AdminFSM.waiting_block_time)


@router.message(AdminFSM.waiting_block_time)
async def block_choose_time(message: Message, state: FSMContext):
    data = await state.get_data()
    t = message.text.strip()
    block_time = None if t.lower() == "all" else t
    await db.block_slot(data["block_master_id"], data["block_date"], block_time)
    await state.clear()
    time_str = "весь день" if not block_time else block_time
    await message.answer(
        f"🚫 Слот заблокирован!\n"
        f"👩 {data['block_master_name']}\n"
        f"📅 {data['block_date']} — {time_str}",
        reply_markup=admin_menu_kb()
    )


# ─────────────────────────────────────────────
#  НАЗАД В ГЛАВНОЕ МЕНЮ
# ─────────────────────────────────────────────
@router.message(F.text == "🔙 Главное меню")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    is_adm = is_admin(message.from_user.id) or (user and user["is_admin"])
    await message.answer("Главное меню:", reply_markup=main_menu_kb(is_adm))
