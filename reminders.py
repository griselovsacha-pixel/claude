"""
Планировщик напоминаний. Запускается как отдельная задача asyncio.
Проверяет записи каждые 10 минут и отправляет напоминания.
"""
import asyncio
import logging
from aiogram import Bot
from database import db
from utils.helpers import format_booking

logger = logging.getLogger(__name__)


async def reminder_loop(bot: Bot, interval: int = 600):
    """Бесконечный цикл напоминаний (каждые 10 минут)."""
    while True:
        try:
            await send_reminders(bot)
        except Exception as e:
            logger.error(f"Reminder error: {e}")
        await asyncio.sleep(interval)


async def send_reminders(bot: Bot):
    bookings = await db.get_bookings_for_reminders()
    from datetime import datetime, timedelta
    now = datetime.now()

    for b in bookings:
        booking_dt = datetime.strptime(f"{b['booking_date']} {b['booking_time']}", "%Y-%m-%d %H:%M")
        hours_left = (booking_dt - now).total_seconds() / 3600

        if not b["reminded_24h"] and hours_left <= 24:
            text = (
                f"🔔 <b>Напоминание о записи!</b>\n\n"
                f"До вашего визита осталось ~24 часа.\n\n"
                f"💅 {b['service_name']}\n"
                f"👩 {b['master_name']}\n"
                f"📅 {b['booking_date']} в {b['booking_time']}\n\n"
                "Ждём вас! Если планы изменились — отмените запись в боте."
            )
            try:
                await bot.send_message(b["tg_id"], text)
                await db.mark_reminded(b["id"], "reminded_24h")
                logger.info(f"24h reminder sent for booking {b['id']}")
            except Exception as e:
                logger.warning(f"Failed to send 24h reminder: {e}")

        elif b["reminded_24h"] and not b["reminded_2h"] and hours_left <= 2:
            text = (
                f"⏰ <b>Скоро ваш визит!</b>\n\n"
                f"До записи осталось ~2 часа.\n\n"
                f"💅 {b['service_name']}\n"
                f"👩 {b['master_name']}\n"
                f"📅 {b['booking_date']} в {b['booking_time']}\n\n"
                "Не забудьте! Мы вас ждём 💕"
            )
            try:
                await bot.send_message(b["tg_id"], text)
                await db.mark_reminded(b["id"], "reminded_2h")
                logger.info(f"2h reminder sent for booking {b['id']}")
            except Exception as e:
                logger.warning(f"Failed to send 2h reminder: {e}")
