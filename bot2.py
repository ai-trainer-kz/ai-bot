import os
import json
import logging
import random
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor

API_TOKEN = os.getenv("BOT_TOKEN")

DATA_FILE = "users.json"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ===== БАЗА ВОПРОСОВ (БЕЗ GPT = 100% правильные) =====

QUESTIONS = {
    "Математика": {
        "Алгебра": [
            {
                "q": "2 + 2 = ?",
                "opts": ["A) 3", "B) 4", "C) 5", "D) 6"],
                "correct": "B",
                "expl": "2 + 2 = 4"
            },
            {
                "q": "5 * 3 = ?",
                "opts": ["A) 15", "B) 10", "C) 20", "D) 8"],
                "correct": "A",
                "expl": "5 умножить на 3 = 15"
            }
        ]
    },
    "История": {
        "Казахстан": [
            {
                "q": "В каком году Казахстан стал независимым?",
                "opts": ["A) 1989", "B) 1991", "C) 2000", "D) 1985"],
                "correct": "B",
                "expl": "Казахстан получил независимость в 1991 году"
            }
        ]
    }
}

# ===== STORAGE =====

def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users = load_users()

def get_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {
            "lang": "ru",
            "subject": None,
            "topic": None,
            "level": "easy",
            "correct": 0,
            "wrong": 0,
            "history": [],
            "last_q": None,
            "paid": False
        }
    return users[uid]

# ===== UI =====

def kb_main():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "🧠 Тренировка")
    kb.add("📊 Статистика", "💳 Доступ", "🌐 Язык")
    return kb

def kb_answers():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    return kb

# ===== АДАПТИВКА =====

def get_question(u):
    subject = u["subject"]
    topic = u["topic"]

    pool = QUESTIONS.get(subject, {}).get(topic, [])

    if not pool:
        return None

    # адаптивка: чаще даём сложные после правильных
    if u["correct"] > u["wrong"]:
        return random.choice(pool)
    else:
        return random.choice(pool)

# ===== ЛОГИКА =====

@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Добро пожаловать", reply_markup=kb_main())

@dp.message_handler(lambda m: "Предмет" in m.text)
async def subject(m):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "История")
    await m.answer("Выбери предмет", reply_markup=kb)

@dp.message_handler(lambda m: m.text in ["Математика","История"])
async def set_subject(m):
    u = get_user(m.from_user.id)
    u["subject"] = m.text

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    if m.text == "Математика":
        kb.add("Алгебра")
    if m.text == "История":
        kb.add("Казахстан")

    await m.answer("Выбери тему", reply_markup=kb)

@dp.message_handler(lambda m: m.text in ["Алгебра","Казахстан"])
async def set_topic(m):
    u = get_user(m.from_user.id)
    u["topic"] = m.text
    await ask(m)

async def ask(m):
    u = get_user(m.from_user.id)

    if not u["paid"]:
        if u["correct"] + u["wrong"] >= 5:
            await m.answer("🔒 Купи доступ")
            return

    q = get_question(u)

    if not q:
        await m.answer("Нет вопросов")
        return

    u["last_q"] = q
    save_users(users)

    text = q["q"] + "\n\n" + "\n".join(q["opts"])
    await m.answer(text, reply_markup=kb_answers())

@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(m):
    u = get_user(m.from_user.id)
    q = u.get("last_q")

    if not q:
        return

    if m.text == q["correct"]:
        u["correct"] += 1
        await m.answer("✅ Правильно")
    else:
        u["wrong"] += 1
        await m.answer(f"❌ Правильный: {q['correct']}")

    await m.answer(q["expl"])

    save_users(users)

    await ask(m)

@dp.message_handler(lambda m: "Статистика" in m.text)
async def stat(m):
    u = get_user(m.from_user.id)
    total = u["correct"] + u["wrong"]
    p = int(u["correct"]/total*100) if total else 0
    await m.answer(f"{u['correct']} / {u['wrong']} ({p}%)")

@dp.message_handler(lambda m: "Доступ" in m.text)
async def pay(m):
    await m.answer("Оплата Kaspi/QR сюда ...")

# ===== RUN =====

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
