import aiosqlite
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Синглтон: одна БД на весь процесс
# ─────────────────────────────────────────────
_db: Optional[aiosqlite.Connection] = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DATABASE_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


# ─────────────────────────────────────────────
#  Инициализация таблиц
# ─────────────────────────────────────────────
async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY,
            tg_id       INTEGER UNIQUE NOT NULL,
            username    TEXT,
            full_name   TEXT NOT NULL,
            phone       TEXT,
            is_banned   INTEGER DEFAULT 0,
            is_admin    INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS services (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            description TEXT,
            duration    INTEGER NOT NULL,   -- в минутах
            price       INTEGER NOT NULL,   -- в рублях
            category    TEXT NOT NULL,
            is_active   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS masters (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            specialty   TEXT,
            bio         TEXT,
            photo_id    TEXT,
            is_active   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL REFERENCES users(id),
            master_id     INTEGER NOT NULL REFERENCES masters(id),
            service_id    INTEGER NOT NULL REFERENCES services(id),
            booking_date  TEXT NOT NULL,    -- YYYY-MM-DD
            booking_time  TEXT NOT NULL,    -- HH:MM
            status        TEXT DEFAULT 'pending',  -- pending/confirmed/done/cancelled
            comment       TEXT,
            reminded_24h  INTEGER DEFAULT 0,
            reminded_2h   INTEGER DEFAULT 0,
            created_at    TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            booking_id  INTEGER NOT NULL REFERENCES bookings(id),
            rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            text        TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS blocked_slots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            master_id   INTEGER NOT NULL REFERENCES masters(id),
            block_date  TEXT NOT NULL,
            block_time  TEXT,   -- NULL = весь день
            reason      TEXT
        );
    """)
    await db.commit()
    await _seed_data(db)
    logger.info("Database initialized.")


async def _seed_data(db: aiosqlite.Connection):
    """Заполнить начальными данными если БД пустая."""
    cur = await db.execute("SELECT COUNT(*) FROM services")
    count = (await cur.fetchone())[0]
    if count > 0:
        return

    services = [
        ("Классический маникюр", "Обработка кутикулы, придание формы, покрытие лаком", 60, 1200, "Маникюр"),
        ("Аппаратный маникюр", "Аппаратная обработка, педикюр без срезания", 75, 1500, "Маникюр"),
        ("Гель-лак", "Долговременное покрытие гель-лаком до 3 недель", 90, 1800, "Маникюр"),
        ("Наращивание ногтей (гель)", "Моделирование на формах или типсах", 120, 2500, "Наращивание"),
        ("Наращивание (акрил)", "Акриловое моделирование, укрепление", 120, 2800, "Наращивание"),
        ("Коррекция наращенных", "Заполнение отросшей зоны", 90, 1500, "Наращивание"),
        ("Классический педикюр", "Обработка стоп, форма, лак", 70, 1400, "Педикюр"),
        ("Аппаратный педикюр", "Аппаратная обработка стоп", 90, 1800, "Педикюр"),
        ("Педикюр + гель-лак", "Аппаратный педикюр с гель-лаком", 110, 2200, "Педикюр"),
        ("Дизайн (1 ноготь)", "Рисунок, стразы, фольга на 1 ноготь", 15, 100, "Дизайн"),
        ("Дизайн (все ногти)", "Художественный дизайн на все ногти", 60, 800, "Дизайн"),
        ("Снятие покрытия", "Бережное снятие гель-лака", 30, 400, "Прочее"),
        ("Снятие наращивания", "Полное снятие наращенных ногтей", 60, 700, "Прочее"),
        ("SPA-маникюр", "Маникюр + скраб + маска + парафин", 90, 2000, "Уход"),
    ]
    await db.executemany(
        "INSERT INTO services(name,description,duration,price,category) VALUES(?,?,?,?,?)",
        services
    )

    masters = [
        ("Анна Смирнова", "Маникюр, наращивание", "Мастер с 7-летним опытом. Специализируется на сложных дизайнах и наращивании. Победитель городского конкурса 2023.", None),
        ("Мария Козлова", "Маникюр, педикюр, дизайн", "Нежный подход к каждому клиенту. Эксперт в гель-лаке и художественном дизайне.", None),
        ("Екатерина Петрова", "Педикюр, SPA-уход", "Специалист по уходу за стопами и SPA-процедурам. Медицинское образование.", None),
    ]
    await db.executemany(
        "INSERT INTO masters(name,specialty,bio) VALUES(?,?,?)",
        masters
    )

    await db.commit()
    logger.info("Seed data inserted.")


# ─────────────────────────────────────────────
#  USERS
# ─────────────────────────────────────────────
async def upsert_user(tg_id: int, username: str, full_name: str):
    db = await get_db()
    await db.execute("""
        INSERT INTO users(tg_id, username, full_name)
        VALUES(?,?,?)
        ON CONFLICT(tg_id) DO UPDATE SET
            username=excluded.username,
            full_name=excluded.full_name
    """, (tg_id, username, full_name))
    await db.commit()


async def get_user(tg_id: int):
    db = await get_db()
    cur = await db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
    return await cur.fetchone()


async def set_user_phone(tg_id: int, phone: str):
    db = await get_db()
    await db.execute("UPDATE users SET phone=? WHERE tg_id=?", (phone, tg_id))
    await db.commit()


async def get_all_users():
    db = await get_db()
    cur = await db.execute("SELECT * FROM users WHERE is_banned=0")
    return await cur.fetchall()


async def ban_user(tg_id: int, ban: bool = True):
    db = await get_db()
    await db.execute("UPDATE users SET is_banned=? WHERE tg_id=?", (int(ban), tg_id))
    await db.commit()


async def set_admin(tg_id: int, is_admin: bool):
    db = await get_db()
    await db.execute("UPDATE users SET is_admin=? WHERE tg_id=?", (int(is_admin), tg_id))
    await db.commit()


# ─────────────────────────────────────────────
#  SERVICES
# ─────────────────────────────────────────────
async def get_services(category: str = None):
    db = await get_db()
    if category:
        cur = await db.execute(
            "SELECT * FROM services WHERE is_active=1 AND category=? ORDER BY price",
            (category,)
        )
    else:
        cur = await db.execute("SELECT * FROM services WHERE is_active=1 ORDER BY category,price")
    return await cur.fetchall()


async def get_service(service_id: int):
    db = await get_db()
    cur = await db.execute("SELECT * FROM services WHERE id=?", (service_id,))
    return await cur.fetchone()


async def get_service_categories():
    db = await get_db()
    cur = await db.execute("SELECT DISTINCT category FROM services WHERE is_active=1 ORDER BY category")
    rows = await cur.fetchall()
    return [r["category"] for r in rows]


async def toggle_service(service_id: int):
    db = await get_db()
    await db.execute("UPDATE services SET is_active=NOT is_active WHERE id=?", (service_id,))
    await db.commit()


# ─────────────────────────────────────────────
#  MASTERS
# ─────────────────────────────────────────────
async def get_masters(active_only: bool = True):
    db = await get_db()
    if active_only:
        cur = await db.execute("SELECT * FROM masters WHERE is_active=1")
    else:
        cur = await db.execute("SELECT * FROM masters")
    return await cur.fetchall()


async def get_master(master_id: int):
    db = await get_db()
    cur = await db.execute("SELECT * FROM masters WHERE id=?", (master_id,))
    return await cur.fetchone()


# ─────────────────────────────────────────────
#  BOOKINGS
# ─────────────────────────────────────────────
async def create_booking(user_id: int, master_id: int, service_id: int,
                          booking_date: str, booking_time: str, comment: str = None):
    db = await get_db()
    cur = await db.execute("""
        INSERT INTO bookings(user_id, master_id, service_id, booking_date, booking_time, comment)
        VALUES(?,?,?,?,?,?)
    """, (user_id, master_id, service_id, booking_date, booking_time, comment))
    await db.commit()
    return cur.lastrowid


async def get_booking(booking_id: int):
    db = await get_db()
    cur = await db.execute("""
        SELECT b.*, u.full_name as client_name, u.phone as client_phone, u.tg_id,
               s.name as service_name, s.price, s.duration,
               m.name as master_name
        FROM bookings b
        JOIN users u ON b.user_id=u.id
        JOIN services s ON b.service_id=s.id
        JOIN masters m ON b.master_id=m.id
        WHERE b.id=?
    """, (booking_id,))
    return await cur.fetchone()


async def get_user_bookings(tg_id: int, upcoming_only: bool = False):
    db = await get_db()
    today = date.today().isoformat()
    if upcoming_only:
        cur = await db.execute("""
            SELECT b.*, s.name as service_name, s.price, m.name as master_name
            FROM bookings b
            JOIN users u ON b.user_id=u.id
            JOIN services s ON b.service_id=s.id
            JOIN masters m ON b.master_id=m.id
            WHERE u.tg_id=? AND b.booking_date>=? AND b.status NOT IN ('cancelled','done')
            ORDER BY b.booking_date, b.booking_time
        """, (tg_id, today))
    else:
        cur = await db.execute("""
            SELECT b.*, s.name as service_name, s.price, m.name as master_name
            FROM bookings b
            JOIN users u ON b.user_id=u.id
            JOIN services s ON b.service_id=s.id
            JOIN masters m ON b.master_id=m.id
            WHERE u.tg_id=?
            ORDER BY b.booking_date DESC, b.booking_time DESC
        """, (tg_id,))
    return await cur.fetchall()


async def get_master_bookings(master_id: int, booking_date: str):
    db = await get_db()
    cur = await db.execute("""
        SELECT b.booking_time, s.duration
        FROM bookings b
        JOIN services s ON b.service_id=s.id
        WHERE b.master_id=? AND b.booking_date=? AND b.status NOT IN ('cancelled')
        ORDER BY b.booking_time
    """, (master_id, booking_date))
    return await cur.fetchall()


async def get_all_bookings_for_date(booking_date: str):
    db = await get_db()
    cur = await db.execute("""
        SELECT b.*, u.full_name as client_name, u.phone as client_phone,
               s.name as service_name, s.price, s.duration,
               m.name as master_name
        FROM bookings b
        JOIN users u ON b.user_id=u.id
        JOIN services s ON b.service_id=s.id
        JOIN masters m ON b.master_id=m.id
        WHERE b.booking_date=? AND b.status NOT IN ('cancelled')
        ORDER BY b.booking_time, m.name
    """, (booking_date,))
    return await cur.fetchall()


async def update_booking_status(booking_id: int, status: str):
    db = await get_db()
    await db.execute("UPDATE bookings SET status=? WHERE id=?", (status, booking_id))
    await db.commit()


async def cancel_booking(booking_id: int, tg_id: int = None):
    """Отмена записи. Если tg_id передан — проверяем что это запись пользователя."""
    db = await get_db()
    if tg_id:
        await db.execute("""
            UPDATE bookings SET status='cancelled'
            WHERE id=? AND user_id=(SELECT id FROM users WHERE tg_id=?)
        """, (booking_id, tg_id))
    else:
        await db.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (booking_id,))
    await db.commit()


async def is_slot_available(master_id: int, booking_date: str,
                             booking_time: str, service_duration: int) -> bool:
    """Проверка что слот не пересекается с существующими записями."""
    from datetime import datetime, timedelta
    db = await get_db()

    # Проверяем блокировки
    cur = await db.execute("""
        SELECT 1 FROM blocked_slots
        WHERE master_id=? AND block_date=? AND (block_time IS NULL OR block_time=?)
    """, (master_id, booking_date, booking_time))
    if await cur.fetchone():
        return False

    # Получаем все записи мастера на этот день
    existing = await get_master_bookings(master_id, booking_date)
    new_start = datetime.strptime(f"{booking_date} {booking_time}", "%Y-%m-%d %H:%M")
    new_end = new_start + timedelta(minutes=service_duration)

    for row in existing:
        ex_start = datetime.strptime(f"{booking_date} {row['booking_time']}", "%Y-%m-%d %H:%M")
        ex_end = ex_start + timedelta(minutes=row["duration"])
        if new_start < ex_end and new_end > ex_start:
            return False
    return True


async def get_bookings_for_reminders():
    """Записи, которым нужны напоминания."""
    db = await get_db()
    now = datetime.now()
    target_24 = (now + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
    target_2  = (now + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")

    cur = await db.execute("""
        SELECT b.*, u.tg_id, u.full_name as client_name,
               s.name as service_name, m.name as master_name
        FROM bookings b
        JOIN users u ON b.user_id=u.id
        JOIN services s ON b.service_id=s.id
        JOIN masters m ON b.master_id=m.id
        WHERE b.status='confirmed'
          AND ((b.reminded_24h=0 AND datetime(b.booking_date||' '||b.booking_time) <= ?)
            OR (b.reminded_2h=0  AND datetime(b.booking_date||' '||b.booking_time) <= ?))
          AND datetime(b.booking_date||' '||b.booking_time) > datetime('now','localtime')
    """, (target_24, target_2))
    return await cur.fetchall()


async def mark_reminded(booking_id: int, field: str):
    db = await get_db()
    await db.execute(f"UPDATE bookings SET {field}=1 WHERE id=?", (booking_id,))
    await db.commit()


# ─────────────────────────────────────────────
#  REVIEWS
# ─────────────────────────────────────────────
async def add_review(user_id_db: int, booking_id: int, rating: int, text: str = None):
    db = await get_db()
    await db.execute(
        "INSERT INTO reviews(user_id,booking_id,rating,text) VALUES(?,?,?,?)",
        (user_id_db, booking_id, rating, text)
    )
    await db.commit()


async def get_reviews(limit: int = 10):
    db = await get_db()
    cur = await db.execute("""
        SELECT r.*, u.full_name, s.name as service_name, m.name as master_name
        FROM reviews r
        JOIN users u ON r.user_id=u.id
        JOIN bookings b ON r.booking_id=b.id
        JOIN services s ON b.service_id=s.id
        JOIN masters m ON b.master_id=m.id
        ORDER BY r.created_at DESC LIMIT ?
    """, (limit,))
    return await cur.fetchall()


async def has_review(booking_id: int) -> bool:
    db = await get_db()
    cur = await db.execute("SELECT 1 FROM reviews WHERE booking_id=?", (booking_id,))
    return bool(await cur.fetchone())


async def get_master_rating(master_id: int):
    db = await get_db()
    cur = await db.execute("""
        SELECT AVG(r.rating) as avg_rating, COUNT(*) as total
        FROM reviews r
        JOIN bookings b ON r.booking_id=b.id
        WHERE b.master_id=?
    """, (master_id,))
    return await cur.fetchone()


# ─────────────────────────────────────────────
#  STATISTICS (admin)
# ─────────────────────────────────────────────
async def get_stats():
    db = await get_db()
    cur = await db.execute("""
        SELECT
            (SELECT COUNT(*) FROM users) as total_users,
            (SELECT COUNT(*) FROM bookings WHERE status NOT IN ('cancelled')) as total_bookings,
            (SELECT COUNT(*) FROM bookings WHERE status='done') as done_bookings,
            (SELECT COUNT(*) FROM bookings WHERE status='cancelled') as cancelled_bookings,
            (SELECT COALESCE(SUM(s.price),0)
             FROM bookings b JOIN services s ON b.service_id=s.id
             WHERE b.status='done') as total_revenue,
            (SELECT COALESCE(AVG(rating),0) FROM reviews) as avg_rating
    """)
    return await cur.fetchone()


async def get_popular_services(limit: int = 5):
    db = await get_db()
    cur = await db.execute("""
        SELECT s.name, COUNT(*) as cnt
        FROM bookings b JOIN services s ON b.service_id=s.id
        WHERE b.status NOT IN ('cancelled')
        GROUP BY s.id ORDER BY cnt DESC LIMIT ?
    """, (limit,))
    return await cur.fetchall()


async def block_slot(master_id: int, block_date: str, block_time: str = None, reason: str = None):
    db = await get_db()
    await db.execute(
        "INSERT INTO blocked_slots(master_id,block_date,block_time,reason) VALUES(?,?,?,?)",
        (master_id, block_date, block_time, reason)
    )
    await db.commit()
