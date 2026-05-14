from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from datetime import date, timedelta


# ─────────────────────────────────────────────
#  ГЛАВНОЕ МЕНЮ
# ─────────────────────────────────────────────
def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="📅 Записаться")
    builder.button(text="🗒 Мои записи")
    builder.button(text="💰 Услуги и цены")
    builder.button(text="👩‍🎨 Наши мастера")
    builder.button(text="⭐ Отзывы")
    builder.button(text="👤 Мой профиль")
    if is_admin:
        builder.button(text="🔧 Админ-панель")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


def admin_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="📊 Статистика")
    builder.button(text="📋 Записи на сегодня")
    builder.button(text="📆 Записи на дату")
    builder.button(text="✅ Подтвердить запись")
    builder.button(text="📢 Рассылка")
    builder.button(text="🚫 Заблокировать слот")
    builder.button(text="🔙 Главное меню")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


# ─────────────────────────────────────────────
#  INLINE КЛАВИАТУРЫ
# ─────────────────────────────────────────────
def categories_kb(categories: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    icons = {
        "Маникюр": "💅", "Наращивание": "✨", "Педикюр": "🦶",
        "Дизайн": "🎨", "Уход": "🌿", "Прочее": "📌"
    }
    for cat in categories:
        icon = icons.get(cat, "▪️")
        builder.button(text=f"{icon} {cat}", callback_data=f"cat:{cat}")
    builder.adjust(2)
    return builder.as_markup()


def services_kb(services: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in services:
        builder.button(
            text=f"{s['name']} — {s['price']}₽ ({s['duration']} мин)",
            callback_data=f"srv:{s['id']}"
        )
    builder.button(text="🔙 К категориям", callback_data="back:categories")
    builder.adjust(1)
    return builder.as_markup()


def masters_kb(masters: list, show_rating: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for m in masters:
        name = m["name"]
        builder.button(text=f"👩 {name}", callback_data=f"mst:{m['id']}")
    builder.button(text="🔙 К услугам", callback_data="back:services")
    builder.adjust(1)
    return builder.as_markup()


def dates_kb(skip_days: int = 0) -> InlineKeyboardMarkup:
    """Выбор даты: сегодня + 13 дней вперёд, пропуская воскресенья."""
    builder = InlineKeyboardBuilder()
    today = date.today()
    generated = 0
    delta = 0
    while generated < 14:
        d = today + timedelta(days=delta + skip_days)
        delta += 1
        if d.weekday() == 6:  # воскресенье — выходной
            continue
        ru_days = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
        ru_months = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]
        label = f"{ru_days[d.weekday()]} {d.day} {ru_months[d.month-1]}"
        if d == today:
            label = f"Сегодня, {label}"
        elif d == today + timedelta(days=1):
            label = f"Завтра, {label}"
        builder.button(text=label, callback_data=f"date:{d.isoformat()}")
        generated += 1
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(2)
    return builder.as_markup()


def times_kb(available_times: list, booking_date: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in available_times:
        builder.button(text=t, callback_data=f"time:{t}")
    builder.button(text="🔙 Выбрать другую дату", callback_data="back:dates")
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(3)
    return builder.as_markup()


def confirm_booking_kb(booking_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"confirm_bk:{booking_id}")
    builder.button(text="❌ Отменить", callback_data=f"cancel_bk:{booking_id}")
    builder.adjust(2)
    return builder.as_markup()


def my_bookings_kb(bookings: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    status_icons = {
        "pending": "⏳", "confirmed": "✅", "done": "🏁", "cancelled": "❌"
    }
    for b in bookings:
        icon = status_icons.get(b["status"], "▪️")
        label = f"{icon} {b['booking_date']} {b['booking_time']} — {b['service_name']}"
        builder.button(text=label, callback_data=f"view_bk:{b['id']}")
    builder.adjust(1)
    return builder.as_markup()


def booking_detail_kb(booking_id: int, status: str, has_review: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status in ("pending", "confirmed"):
        builder.button(text="❌ Отменить запись", callback_data=f"cancel_bk:{booking_id}")
    if status == "done" and not has_review:
        builder.button(text="⭐ Оставить отзыв", callback_data=f"review:{booking_id}")
    builder.button(text="🔙 Назад", callback_data="my_bookings")
    builder.adjust(1)
    return builder.as_markup()


def rating_kb(booking_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    stars = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
    for i, s in enumerate(stars, 1):
        builder.button(text=s, callback_data=f"rate:{booking_id}:{i}")
    builder.adjust(5)
    return builder.as_markup()


def admin_booking_kb(booking_id: int, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "pending":
        builder.button(text="✅ Подтвердить", callback_data=f"adm_confirm:{booking_id}")
    if status in ("pending", "confirmed"):
        builder.button(text="✅ Отметить выполненной", callback_data=f"adm_done:{booking_id}")
        builder.button(text="❌ Отменить", callback_data=f"adm_cancel:{booking_id}")
    builder.adjust(1)
    return builder.as_markup()


def master_info_kb(master_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться к этому мастеру", callback_data=f"book_master:{master_id}")
    builder.button(text="🔙 Назад", callback_data="back:masters_list")
    builder.adjust(1)
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    return builder.as_markup()


def share_phone_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Поделиться номером", request_contact=True)
    builder.button(text="❌ Пропустить")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
