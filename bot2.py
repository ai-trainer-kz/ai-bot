import os
import json
import logging
import openai
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor

# ====== КЛЮЧИ ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

# ====== ЛОГИ ======
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ====== ФАЙЛ ДАННЫХ ======
DATA_FILE = "users.json"

def load_users():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_users():
    with open(DATA_FILE, "w") as f:
        json.dump(users, f)

users = load_users()

# ====== КНОПКИ ======
start_kb = ReplyKeyboardMarkup(resize_keyboard=True)
start_kb.add("🚀 Начать", "📊 Профиль")
start_kb.add("▶️ Тест")

subjects_kb = ReplyKeyboardMarkup(resize_keyboard=True)
subjects_kb.add("📐 Математика", "📜 История", "🧬 Биология")
subjects_kb.add("⚛️ Физика", "🧪 Химия", "🌍 География")
subjects_kb.add("📚 Литература", "🇬🇧 Английский", "🇰🇿 Қазақ тілі")

levels_kb = ReplyKeyboardMarkup(resize_keyboard=True)
levels_kb.add("🟢 Лёгкий", "🟡 Средний", "🔴 Сложный")
levels_kb.add("➡️ Начать тест")

# ====== PROMPT ======
SYSTEM_PROMPT = """
Ты AI-тренер как Duolingo.

Правила:
- 1 вопрос
- коротко
- проверка: правильно/неправильно
- без объяснений
- потом новый вопрос
"""

# ====== XP ======
def add_xp(user, correct):
    if correct:
        user["xp"] += 10
        user["streak"] += 1
    else:
        user["streak"] = 0

    if user["xp"] >= user["level"] * 50:
        user["level"] += 1
        return True
    return False

# ====== СТАРТ ======
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    uid = str(msg.from_user.id)

    if uid not in users:
        users[uid] = {
            "xp": 0,
            "level": 1,
            "streak": 0
        }
        save_users()

    await msg.answer("Привет! Я AI-тренер 💪", reply_markup=start_kb)

# ====== ПРОФИЛЬ ======
@dp.message_handler(lambda msg: msg.text == "📊 Профиль")
async def profile(msg: types.Message):
    uid = str(msg.from_user.id)
    u = users.get(uid)

    text = f"""
📊 Профиль:

🏆 Уровень: {u['level']}
⭐ XP: {u['xp']}
🔥 Серия: {u['streak']}
"""
    await msg.answer(text)

# ====== НАЧАТЬ ======
@dp.message_handler(lambda msg: "начать" in msg.text.lower())
async def start_test(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users.get(uid)

    if not user:
        return

    if "subject" not in user or "difficulty" not in user:
        await msg.answer("Сначала выбери предмет и уровень 👆")
        return

    prompt = f"Задай вопрос по теме {user['subject']}, уровень {user['difficulty']}"

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    q = response.choices[0].message.content
    user["last_question"] = q
    save_users()

    await msg.answer(q)
# ====== ПРЕДМЕТ ======
@dp.message_handler(lambda msg: msg.text in [
    "📐 Математика","📜 История","🧬 Биология",
    "⚛️ Физика","🧪 Химия","🌍 География",
    "📚 Литература","🇬🇧 Английский","🇰🇿 Қазақ тілі"
])
async def choose_level(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["subject"] = msg.text
    save_users()
    await msg.answer("Выбери уровень:", reply_markup=levels_kb)

@dp.message_handler(lambda msg: msg.text in ["📐 Математика", "📜 История", "🧬 Биология", "🇰🇿 Қазақ тілі"])
async def choose_subject(msg: types.Message):
    uid = str(msg.from_user.id)

    if uid not in users:
        users[uid] = {}

    users[uid]["subject"] = msg.text
    save_users()

    await msg.answer("Выбери уровень:", reply_markup=level_kb)

# ====== УРОВЕНЬ ======
@dp.message_handler(lambda msg: msg.text in ["🟢 Лёгкий","🟡 Средний","🔴 Сложный"])
async def start_training(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users[uid]

    user["difficulty"] = msg.text

    prompt = f"Задай вопрос по теме {user['subject']}, уровень {msg.text}"

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    q = response.choices[0].message.content
    user["last_question"] = q
    save_users()

    await msg.answer(q)

# ====== ОТВЕТ ======
@dp.message_handler()
async def handle_answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users.get(uid)

    if not user or "last_question" not in user:
        return

    prompt = f"""
Вопрос: {user['last_question']}
Ответ: {msg.text}

Проверь коротко и задай новый вопрос.
"""

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    text = response.choices[0].message.content

    correct = "Правильно" in text

    level_up = add_xp(user, correct)

    user["last_question"] = text
    save_users()

    stats = f"\n\n⭐ XP: {user['xp']} | 🔥 {user['streak']}"

    await msg.answer(text + stats)

    if level_up:
        await msg.answer(f"🏆 Новый уровень: {user['level']}!")

# ====== ЗАПУСК ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
