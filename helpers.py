from datetime import datetime, timedelta, date
from config import WORK_START_HOUR, WORK_END_HOUR, SLOT_DURATION


def generate_time_slots(start_hour: int = WORK_START_HOUR,
                         end_hour: int = WORK_END_HOUR,
                         slot_minutes: int = SLOT_DURATION) -> list:
    """Генерирует все возможные временные слоты."""
    slots = []
    current = datetime.now().replace(hour=start_hour, minute=0, second=0, microsecond=0)
    end = current.replace(hour=end_hour)
    while current < end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=slot_minutes)
    return slots


def get_available_slots(booked: list, service_duration: int,
                         booking_date: str,
                         start_hour: int = WORK_START_HOUR,
                         end_hour: int = WORK_END_HOUR) -> list:
    """
    Возвращает список свободных слотов с учётом уже занятых.
    booked — список dict с ключами booking_time и duration.
    """
    today = date.today().isoformat()
    now = datetime.now()
    all_slots = generate_time_slots(start_hour, end_hour)
    free = []

    for slot_str in all_slots:
        slot_dt = datetime.strptime(f"{booking_date} {slot_str}", "%Y-%m-%d %H:%M")
        # Прошедшее время не предлагаем (+ буфер 30 мин)
        if booking_date == today and slot_dt <= now + timedelta(minutes=30):
            continue
        slot_end = slot_dt + timedelta(minutes=service_duration)
        end_limit = slot_dt.replace(hour=end_hour, minute=0)
        if slot_end > end_limit:
            continue

        # Проверяем пересечения
        busy = False
        for b in booked:
            ex_start = datetime.strptime(f"{booking_date} {b['booking_time']}", "%Y-%m-%d %H:%M")
            ex_end = ex_start + timedelta(minutes=b["duration"])
            if slot_dt < ex_end and slot_end > ex_start:
                busy = True
                break
        if not busy:
            free.append(slot_str)
    return free


def format_booking(b, show_status: bool = True) -> str:
    """Красивое отображение записи."""
    status_map = {
        "pending":   "⏳ Ожидает подтверждения",
        "confirmed": "✅ Подтверждена",
        "done":      "🏁 Выполнена",
        "cancelled": "❌ Отменена",
    }
    ru_months = ["","января","февраля","марта","апреля","мая","июня",
                 "июля","августа","сентября","октября","ноября","декабря"]
    d = datetime.strptime(b["booking_date"], "%Y-%m-%d")
    date_str = f"{d.day} {ru_months[d.month]} {d.year}"

    lines = [
        f"<b>📅 {date_str} в {b['booking_time']}</b>",
        f"💅 <b>Услуга:</b> {b['service_name']}",
        f"👩 <b>Мастер:</b> {b['master_name']}",
        f"💰 <b>Стоимость:</b> {b['price']}₽",
    ]
    if show_status:
        lines.append(f"📌 <b>Статус:</b> {status_map.get(b['status'], b['status'])}")
    if b.get("comment"):
        lines.append(f"💬 <b>Комментарий:</b> {b['comment']}")
    return "\n".join(lines)


def stars(rating: float) -> str:
    full = int(round(rating))
    return "⭐" * full + "☆" * (5 - full)


def format_date_ru(date_str: str) -> str:
    ru_months = ["","января","февраля","марта","апреля","мая","июня",
                 "июля","августа","сентября","октября","ноября","декабря"]
    ru_days = ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{ru_days[d.weekday()]}, {d.day} {ru_months[d.month]}"
