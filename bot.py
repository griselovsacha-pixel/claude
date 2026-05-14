import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database.db import init_db
from handlers import client, admin, booking, profile, reviews
from middlewares.throttling import ThrottlingMiddleware
from utils.reminders import reminder_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.message.middleware(ThrottlingMiddleware(limit=1.0))

    dp.include_router(client.router)
    dp.include_router(admin.router)
    dp.include_router(booking.router)
    dp.include_router(profile.router)
    dp.include_router(reviews.router)

    logger.info("Bot started!")
    await bot.delete_webhook(drop_pending_updates=True)

    # Запускаем планировщик напоминаний параллельно
    import asyncio
    reminder_task = asyncio.create_task(reminder_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
