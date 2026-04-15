import os
import logging
from datetime import datetime, timedelta

import psycopg2
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ADMIN_ID = 8398266271
KASPI_NUMBER = "4400430352720152"
SUPPORT = "@ai_teacher1_support"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ===== DB =====
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT,
    lang TEXT,
    subject TEXT,
    level TEXT,
    step TEXT,
    q INTEGER DEFAULT 0,
    score INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0,
    premium BOOLEAN DEFAULT FALSE,
    expires TIMESTAMP,
    free_left INTEGER DEFAULT 10,
    last TEXT
)
""")
conn.commit()


# ===== UTILS =====
def get_user(uid):
    cursor.execute("SELECT * FROM users WHERE id=%s", (uid,))
    return cursor.fetchone()


def create_user(uid, name):
    cursor.execute("""
    INSERT INTO users (id, name, lang, step)
    VALUES (%s, %s, 'ru', 'lang')
    ON CONFLICT (id) DO NOTHING
    """, (uid, name))
    conn.commit()


def update(uid, field, value):
    cursor.execute(f"UPDATE users SET {field}=%s WHERE id=%s", (value, uid))
    conn.commit()


# ===== КНОПКИ =====
def lang_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Русский 🇷🇺", "Қазақ 🇰🇿")
    return kb


def subject_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📐 Математика", "📖 История", "🧪 Химия")
    return kb


def level_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Лёгкий", "🟡 Средний", "🔴 Сложный")
    return kb


def control_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    kb.add("⬅️ Назад", "🏠 Домой")
    return kb


def pay_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💳 Я оплатил", "🏠 Домой")
    return kb


def admin_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="7 дней", callback_data=f"give7_{uid}"),
            InlineKeyboardButton(text="30 дней", callback_data=f"give30_{uid}")
        ]
    ])


# ===== START =====
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    uid = str(msg.from_user.id)
    name = msg.from_user.full_name

    create_user(uid, name)

    await msg.answer("Выбери язык 🌍", reply_markup=lang_kb())


# ===== LANG =====
@dp.message_handler(lambda m: "🇷🇺" in m.text or "🇰🇿" in m.text)
async def set_lang(msg: types.Message):
    uid = str(msg.from_user.id)

    lang = "ru" if "🇷🇺" in msg.text else "kz"

    update(uid, "lang", lang)
    update(uid, "step", "subject")

    await msg.answer("Выбери предмет 📚", reply_markup=subject_kb())


# ===== SUBJECT =====
@dp.message_handler(lambda m: m.text.startswith("📐") or m.text.startswith("📖") or m.text.startswith("🧪"))
async def set_subject(msg: types.Message):
    uid = str(msg.from_user.id)

    update(uid, "subject", msg.text)
    update(uid, "step", "level")

    await msg.answer("Выбери уровень 🎯", reply_markup=level_kb())


# ===== LEVEL =====
@dp.message_handler(lambda m: "🟢" in m.text or "🟡" in m.text or "🔴" in m.text)
async def set_level(msg: types.Message):
    uid = str(msg.from_user.id)

    update(uid, "level", msg.text)
    update(uid, "step", "test")
    update(uid, "q", 0)
    update(uid, "score", 0)

    await send_q(msg)


# ===== ACCESS =====
def has_access(user):
    premium = user[10]
    expires = user[11]
    free = user[12]

    if premium and expires and datetime.now() < expires:
        return True

    if free and free > 0:
        return True

    return False


# ===== QUESTION =====
async def send_q(msg):
    uid = str(msg.from_user.id)
    user = get_user(uid)

    if not has_access(user):
        await msg.answer("❌ Нет доступа\n💎 Купи доступ", reply_markup=pay_kb())
        return

    q_count = user[6]

    if q_count >= 10:
        await finish(msg)
        return

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"ЕНТ вопрос {user[3]} {user[4]} 4 варианта A B C D правильный ответ"
            }]
        )
        q = res.choices[0].message.content
    except:
        q = "2+2=?\nA.3\nB.4\nC.5\nD.6"

    update(uid, "last", q)

    await msg.answer(q, reply_markup=control_kb())


# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = get_user(uid)

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"{user[13]} ответ {msg.text} объясни"
            }]
        )
        txt = res.choices[0].message.content
    except:
        txt = "Правильный ответ: B"

    if "B" in txt:
        update(uid, "score", user[7] + 1)

    # уменьшаем free
    if user[12] > 0:
        update(uid, "free_left", user[12] - 1)

    update(uid, "q", user[6] + 1)

    await msg.answer(txt)
    await send_q(msg)


# ===== FINISH =====
async def finish(msg):
    uid = str(msg.from_user.id)
    user = get_user(uid)

    update(uid, "total", user[8] + 1)

    await msg.answer(f"🏁 Результат: {user[7]}/10")

    if not user[10]:
        await ask_pay(msg)


# ===== PAYMENT =====
async def ask_pay(msg):
    await msg.answer(
        f"💳 Kaspi: {KASPI_NUMBER}\n7 дней — 5000₸\n30 дней — 10000₸\n\n{SUPPORT}",
        reply_markup=pay_kb()
    )


@dp.message_handler(lambda m: "оплат" in m.text.lower())
async def paid(msg: types.Message):
    await bot.send_message(
        ADMIN_ID,
        f"Оплата от {msg.from_user.full_name} ({msg.from_user.id})",
        reply_markup=admin_kb(msg.from_user.id)
    )


@dp.callback_query_handler(lambda c: "give" in c.data)
async def give(call):
    uid = call.data.split("_")[1]

    days = 7 if "7" in call.data else 30

    cursor.execute("""
    UPDATE users
    SET premium=TRUE,
        expires=%s
    WHERE id=%s
    """, (datetime.now() + timedelta(days=days), uid))
    conn.commit()

    await bot.send_message(uid, "✅ Доступ активирован")


# ===== BACK =====
@dp.message_handler(lambda m: "Назад" in m.text)
async def back(msg: types.Message):
    await msg.answer("Назад", reply_markup=subject_kb())


# ===== HOME =====
@dp.message_handler(lambda m: "Домой" in m.text)
async def home(msg: types.Message):
    await start(msg)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
