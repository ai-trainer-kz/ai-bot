import os
import json
import logging
import sqlite3
import openai
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ======================
# НАСТРОЙКИ
# ======================

API_TOKEN = "TOKEN"
ADMIN_ID = 8398266271

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

dp = Dispatcher(bot)

# ======================
# БАЗА
# ======================

conn = sqlite3.connect("db.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    premium INTEGER DEFAULT 0,
    expires TEXT,
    total_score INTEGER DEFAULT 0,
    tests_passed INTEGER DEFAULT 0
)
""")

conn.commit()

# ======================
# STATE
# ======================

state = {}

# ======================
# КНОПКИ
# ======================

def kb_lang():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Русский 🇷🇺", "Қазақша 🇰🇿")
    return kb

def kb_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🚀 Начать тест")
    kb.add("👤 Кабинет", "🏆 Рейтинг")
    kb.add("💎 Купить доступ", "🏠 Домой")
    return kb

def kb_subjects():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📐 Математика", "🧪 Химия")
    kb.add("🧬 Биология", "📜 История")
    kb.add("🇰🇿 Қазақ тілі", "🔬 Физика")
    kb.add("⬅️ Назад", "🏠 Домой")
    return kb

def kb_levels():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Лёгкий", "🟡 Средний", "🔴 Сложный")
    kb.add("⬅️ Назад", "🏠 Домой")
    return kb

def kb_answers():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    kb.add("⬅️ Назад","🏠 Домой")
    return kb

def pay_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Я оплатил", callback_data="paid"))
    return kb

def admin_kb(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("7 дней", callback_data=f"give7_{user_id}"),
        InlineKeyboardButton("30 дней", callback_data=f"give30_{user_id}")
    )
    return kb

# ======================
# GPT ВОПРОСЫ
# ======================

async def generate_question(subject, lang):
    prompt = f"""
Сгенерируй 1 тестовый вопрос по предмету {subject} на языке {lang}.
Формат строго:
Вопрос
A. ...
B. ...
C. ...
D. ...
Ответ: A/B/C/D
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}]
        )

        text = response.choices[0].message.content

        lines = text.split("\n")
        q = lines[0]
        answers = [lines[1][3:], lines[2][3:], lines[3][3:], lines[4][3:]]
        correct = lines[5].split(":")[1].strip()

        return {"q": q, "a": answers, "correct": correct}

    except:
        return {"q":"Ошибка генерации","a":["1","2","3","4"],"correct":"A"}

# ======================
# ДОСТУП
# ======================

def check_access(uid):
    cursor.execute("SELECT premium, expires FROM users WHERE id=?", (uid,))
    row = cursor.fetchone()

    if row and row[0] and row[1]:
        if datetime.now() < datetime.fromisoformat(row[1]):
            return True
    return False

# ======================
# СТАРТ
# ======================

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    cursor.execute("INSERT OR IGNORE INTO users(id) VALUES(?)",(message.from_user.id,))
    conn.commit()

    state[message.from_user.id] = {"step":"lang"}

    await message.answer("Выбери язык 🌍", reply_markup=kb_lang())

# ======================
# ОСНОВНАЯ ЛОГИКА
# ======================

@dp.message_handler()
async def main(message: types.Message):
    uid = message.from_user.id
    text = message.text

    if uid not in state:
        return await start(message)

    s = state[uid]

    if text == "🏠 Домой":
        s["step"] = "menu"
        return await message.answer("Главное меню", reply_markup=kb_menu())

    # язык
    if s["step"] == "lang":
        s["lang"] = "ru" if "Русский" in text else "kz"
        s["step"] = "menu"
        return await message.answer("Готово 👍", reply_markup=kb_menu())

    # меню
    if s["step"] == "menu":

        if text == "👤 Кабинет":
            cursor.execute("SELECT total_score, tests_passed, expires FROM users WHERE id=?", (uid,))
            data = cursor.fetchone()

            return await message.answer(
                f"👤 Кабинет\n\n"
                f"Тестов: {data[1]}\n"
                f"Баллы: {data[0]}\n"
                f"Доступ до: {data[2]}"
            )

        if text == "🏆 Рейтинг":
            cursor.execute("SELECT id, total_score FROM users ORDER BY total_score DESC LIMIT 10")
            rows = cursor.fetchall()

            text_r = "🏆 ТОП 10\n\n"
            for i, r in enumerate(rows):
                text_r += f"{i+1}. {r[0]} — {r[1]}\n"

            return await message.answer(text_r)

        if text == "🚀 Начать тест":
            if not check_access(uid):
                return await message.answer("❌ Нет доступа")

            s["step"] = "subject"
            return await message.answer("Выбери предмет", reply_markup=kb_subjects())

        if text == "💎 Купить доступ":
            return await message.answer(
                "Kaspi:\n87001234567\n\n7 дней — 5000₸\n30 дней — 10000₸",
                reply_markup=pay_kb()
            )

    # предмет
    if s["step"] == "subject":

        if "Назад" in text:
            s["step"] = "menu"
            return await message.answer("Меню", reply_markup=kb_menu())

        subject = text.split(" ",1)[-1]
        s["subject"] = subject
        s["step"] = "level"

        return await message.answer("Выбери уровень", reply_markup=kb_levels())

    # уровень
    if s["step"] == "level":

        if "Назад" in text:
            s["step"] = "subject"
            return await message.answer("Предмет", reply_markup=kb_subjects())

        s["q"] = 0
        s["score"] = 0
        s["step"] = "quiz"

        return await send_q(message)

    # тест
    if s["step"] == "quiz":

        if text not in ["A","B","C","D"]:
            return

        if text == s["current"]["correct"]:
            s["score"] += 1

        s["q"] += 1

        if s["q"] >= 5:
            cursor.execute("""
            UPDATE users
            SET total_score = total_score + ?, tests_passed = tests_passed + 1
            WHERE id=?
            """, (s["score"], uid))
            conn.commit()

            s["step"] = "menu"

            return await message.answer(
                f"Результат: {s['score']}/5",
                reply_markup=kb_menu()
            )

        return await send_q(message)

# ======================
# ВОПРОС
# ======================

async def send_q(message):
    uid = message.from_user.id
    s = state[uid]

    q = await generate_question(s["subject"], s["lang"])
    s["current"] = q

    text = f"{q['q']}\n\n"
    text += f"A. {q['a'][0]}\nB. {q['a'][1]}\nC. {q['a'][2]}\nD. {q['a'][3]}"

    await message.answer(text, reply_markup=kb_answers())

# ======================
# ОПЛАТА
# ======================

@dp.callback_query_handler(lambda c: c.data == "paid")
async def paid(callback: types.CallbackQuery):
    uid = callback.from_user.id

    await bot.send_message(
        ADMIN_ID,
        f"Заявка: {uid}",
        reply_markup=admin_kb(uid)
    )

    await callback.answer("Отправлено админу")

# ======================
# АДМИН
# ======================

@dp.callback_query_handler(lambda c: c.data.startswith("give7_"))
async def give7(callback: types.CallbackQuery):
    uid = int(callback.data.split("_")[1])
    expires = datetime.now() + timedelta(days=7)

    cursor.execute("UPDATE users SET premium=1, expires=? WHERE id=?", (expires.isoformat(), uid))
    conn.commit()

    await bot.send_message(uid, "Доступ 7 дней активирован")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("give30_"))
async def give30(callback: types.CallbackQuery):
    uid = int(callback.data.split("_")[1])
    expires = datetime.now() + timedelta(days=30)

    cursor.execute("UPDATE users SET premium=1, expires=? WHERE id=?", (expires.isoformat(), uid))
    conn.commit()

    await bot.send_message(uid, "Доступ 30 дней активирован")
    await callback.answer()

# ======================
# СТАРТ
# ======================

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
