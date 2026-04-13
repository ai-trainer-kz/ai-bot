import os
import logging
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor

BOT_TOKEN = os.getenv("BOT_TOKEN")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ===== USERS =====
users = {}

def save_users():
    with open("users.json", "w") as f:
        json.dump(users, f)

def load_users():
    global users
    try:
        with open("users.json", "r") as f:
            users = json.load(f)
    except:
        users = {}

load_users()

# ===== КНОПКИ =====

main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("🚀 Начать", "▶️ Тест")
main_kb.add("📊 Профиль")

subjects_kb = ReplyKeyboardMarkup(resize_keyboard=True)
subjects_kb.add("Математика", "История")
subjects_kb.add("Биология", "Қазақ тілі")

level_kb = ReplyKeyboardMarkup(resize_keyboard=True)
level_kb.add("Лёгкий", "Средний", "Сложный")

start_test_kb = ReplyKeyboardMarkup(resize_keyboard=True)
start_test_kb.add("➡️ Начать тест")

answers_kb = ReplyKeyboardMarkup(resize_keyboard=True)
answers_kb.add("A", "B", "C", "D")
answers_kb.add("🔙 Назад")

# ===== СТАРТ =====

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("Привет! Я AI-тренер 💪", reply_markup=main_kb)

# ===== МЕНЮ =====

@dp.message_handler(lambda msg: msg.text == "🚀 Начать" or msg.text == "▶️ Тест")
async def choose_subject(msg: types.Message):
    await msg.answer("Выбери предмет 👇", reply_markup=subjects_kb)

@dp.message_handler(lambda msg: msg.text in ["Математика", "История", "Биология", "Қазақ тілі"])
async def choose_level(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid] = users.get(uid, {})
    users[uid]["subject"] = msg.text
    save_users()

    await msg.answer("Выбери уровень:", reply_markup=level_kb)

@dp.message_handler(lambda msg: msg.text in ["Лёгкий", "Средний", "Сложный"])
async def start_test_menu(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["difficulty"] = msg.text
    save_users()

    await msg.answer("Нажми ➡️ Начать тест", reply_markup=start_test_kb)

# ===== НАЧАТЬ ТЕСТ =====

@dp.message_handler(lambda msg: msg.text == "➡️ Начать тест")
async def send_question(msg: types.Message):
    uid = str(msg.from_user.id)

    if uid not in users or "subject" not in users[uid]:
        await msg.answer("Сначала выбери предмет 👇")
        return

    # простой вопрос (пока без GPT)
    question = "Сколько будет 2 + 2?\n\nA) 3\nB) 4\nC) 5\nD) 6"

    users[uid]["correct"] = "B"
    save_users()

    await msg.answer(question, reply_markup=answers_kb)

# ===== НАЗАД =====

@dp.message_handler(lambda msg: msg.text == "🔙 Назад")
async def go_back(msg: types.Message):
    uid = str(msg.from_user.id)

    if uid in users:
        users[uid].pop("subject", None)
        users[uid].pop("difficulty", None)
        save_users()

    await msg.answer("Выбери предмет 👇", reply_markup=subjects_kb)

# ===== ОТВЕТ =====

@dp.message_handler(lambda msg: msg.text in ["A", "B", "C", "D"])
async def check_answer(msg: types.Message):
    uid = str(msg.from_user.id)

    correct = users.get(uid, {}).get("correct")

    if not correct:
        await msg.answer("Сначала начни тест")
        return

    if msg.text == correct:
        await msg.answer("✅ Правильно!")
    else:
        await msg.answer(f"❌ Неправильно. Ответ: {correct}")

# ===== ПРОФИЛЬ =====

@dp.message_handler(lambda msg: msg.text == "📊 Профиль")
async def profile(msg: types.Message):
    await msg.answer("📊 Профиль:\n🏆 Уровень: 1\n⭐ XP: 0\n🔥 Серия: 0")

# ===== ЗАПУСК =====

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
