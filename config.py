import os

# =================== НАСТРОЙКИ БОТА ===================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ID администраторов (можно добавить несколько)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")]

# =================== НАСТРОЙКИ САЛОНА ===================
SALON_NAME = "💅 Nail Studio"
SALON_ADDRESS = "ул. Красоты, 1, г. Москва"
SALON_PHONE = "+7 (999) 123-45-67"
SALON_INSTAGRAM = "@nail_studio"
SALON_WORK_HOURS = "Пн–Сб: 09:00–20:00, Вс: 10:00–18:00"

# =================== РАБОЧЕЕ ВРЕМЯ ===================
WORK_START_HOUR = 9    # Начало приема
WORK_END_HOUR = 20     # Конец приема
SLOT_DURATION = 60     # Длительность слота в минутах

# =================== НАПОМИНАНИЯ ===================
REMINDER_HOURS_BEFORE = 24   # За сколько часов напоминать о записи
REMINDER_HOURS_BEFORE_2 = 2  # Второе напоминание

# =================== БД ===================
DATABASE_PATH = "manicure.db"
