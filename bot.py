import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web  # Додано для міні-сайту

from config import BOT_TOKEN
from db import init_db
from handlers import client, admin, booking, profile, reviews
from middlewares.throttling import ThrottlingMiddleware
from utils.reminders import reminder_loop

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# --- МІНІ-САЙТ ДЛЯ ЗАПОБІГАННЯ ПРИСПЛЯННЮ ---
async def handle(request):
    return web.Response(text="Bot is running! Hamer Project Active.")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)  # Порт 8080 стандартний для Render
    await site.start()
    logger.info("Web server started on port 8080")

# --- ОСНОВНА ФУНКЦІЯ ---
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

    # Запускаємо веб-сервер
    await start_web_server()

    # Запускаємо планувальник нагадувань
    reminder_task = asyncio.create_task(reminder_loop(bot))
    
    try:
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
