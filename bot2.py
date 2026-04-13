import os
import logging
import json

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor

from openai import OpenAI

# ====== КЛЮЧИ ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ====== БАЗА ======
DATA_FILE = "users.json"

def load_users():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()

# ====== GPT ======
SYSTEM_PROMPT = """
Ты — AI-тренер для подготовки к ЕНТ.
Задавай 1 вопрос с 4 вариантами ответа (A, B, C, D).
Не пиши ответ сразу.
После ответа:
- скажи правильно или нет
- дай правильный ответ
- коротко объясни
"""

# ====== КНОПКИ ======
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("🚀 Начать", "▶️ Тест")
main_kb.add("📊 Профиль")

subjects_kb = ReplyKeyboardMarkup(resize_keyboard=True)
subjects_kb.add("Математика", "История")
subjects_kb.add("Биология", "Қазақ тілі")
subjects_kb.add("Физика", "Химия")  # ДОБАВИЛИ

level_kb = ReplyKeyboardMarkup(resize_keyboard=True)
level_kb.add("Лёгкий", "Средний", "Сложный")

start_test_kb = ReplyKeyboardMarkup(resize_keyboard=True)
start_test_kb.add("➡️ Начать тест")
start_test_kb.add("🔙 Назад")

answers_kb = ReplyKeyboardMarkup(resize_keyboard=True)
answers_kb.add("A", "B", "C", "D")
answers_kb.add("🔙 Назад", "🛑 Завершить")  # ДОБАВИЛИ

# ====== СТАРТ ======
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("Привет! Я AI-тренер 💪", reply_markup=main_kb)

# ====== МЕНЮ ======
@dp.message_handler(lambda msg: msg.text in ["🚀 Начать", "▶️ Тест"])
async def go_to_subject(msg: types.Message):
    await msg.answer("Выбери предмет 👇", reply_markup=subjects_kb)

# ====== ПРЕДМЕТ ======
@dp.message_handler(lambda msg: msg.text in ["Математика","История","Биология","Қазақ тілі","Физика","Химия"])
async def choose_subject(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid] = users.get(uid, {})
    users[uid]["subject"] = msg.text
    save_users()

    await msg.answer("Выбери уровень:", reply_markup=level_kb)

# ====== УРОВЕНЬ ======
@dp.message_handler(lambda msg: msg.text in ["Лёгкий","Средний","Сложный"])
async def choose_level(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid]["difficulty"] = msg.text
    save_users()

    await msg.answer("Нажми ➡️ Начать тест", reply_markup=start_test_kb)

# ====== НАЗАД ======
@dp.message_handler(lambda msg: msg.text == "🔙 Назад")
async def go_back(msg: types.Message):
    uid = str(msg.from_user.id)

    if uid in users:
        users[uid].pop("subject", None)
        users[uid].pop("difficulty", None)
        users[uid].pop("last_question", None)
        save_users()

    await msg.answer("Выбери предмет 👇", reply_markup=subjects_kb)

# ====== ЗАВЕРШИТЬ ======
@dp.message_handler(lambda msg: msg.text == "🛑 Завершить")
async def stop_test(msg: types.Message):
    await msg.answer("Тест завершён 👍", reply_markup=main_kb)

# ====== СТАРТ ТЕСТА ======
@dp.message_handler(lambda msg: msg.text == "➡️ Начать тест")
async def start_test(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users.get(uid)

    if not user or "subject" not in user or "difficulty" not in user:
        await msg.answer("Сначала выбери предмет и уровень 👆")
        return

    prompt = f"Задай вопрос по теме {user['subject']}, уровень {user['difficulty']}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    question = response.choices[0].message.content

    user["last_question"] = question
    save_users()

    await msg.answer(question, reply_markup=answers_kb)

# ====== ОТВЕТ ======
@dp.message_handler(lambda msg: msg.text in ["A","B","C","D"])
async def handle_answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users.get(uid)

    if not user or "last_question" not in user:
        await msg.answer("Сначала начни тест 👆")
        return

    prompt = f"""
Вопрос:
{user['last_question']}

Ответ пользователя:
{msg.text}

Скажи:
1. Правильно или нет
2. Правильный ответ
3. Короткое объяснение
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    result = response.choices[0].message.content

    prompt2 = f"Задай следующий вопрос по теме {user['subject']}, уровень {user['difficulty']}"

    response2 = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt2}
        ]
    )

    new_q = response2.choices[0].message.content

    user["last_question"] = new_q
    user["xp"] = user.get("xp", 0) + 10
    save_users()

    await msg.answer(result)
    await msg.answer(new_q, reply_markup=answers_kb)

# ====== ПРОФИЛЬ ======
@dp.message_handler(lambda msg: msg.text == "📊 Профиль")
async def profile(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid] = users.get(uid, {"xp": 0, "level": 1, "streak": 0})
    user = users[uid]

    text = f"""
📊 Профиль:

🏆 Уровень: {user.get("level", 1)}
⭐ XP: {user.get("xp", 0)}
🔥 Серия: {user.get("streak", 0)}
"""
    await msg.answer(text)

# ====== ЗАПУСК ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
