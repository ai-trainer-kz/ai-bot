import logging
import os
import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from openai import OpenAI

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

client = OpenAI(api_key=OPENAI_API_KEY)

# ===== БАЗА =====
user_mode = {}
user_level = {}
user_score = {}
user_question = {}
user_test_questions = {}
premium_users = set()

# ===== КНОПКИ =====
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("🤖 AI")
main_kb.add("📝 Тест")
main_kb.add("💎 Премиум")

level_kb = ReplyKeyboardMarkup(resize_keyboard=True)
level_kb.add("🟢 Легкий", "🟡 Средний", "🔴 Сложный")

answer_kb = ReplyKeyboardMarkup(resize_keyboard=True)
answer_kb.add("A", "B", "C", "D")

# ===== ВОПРОСЫ =====
questions = {
    "easy": [
        {"q": "2+2=?", "options": ["3", "4", "5", "6"], "a": "B"},
        {"q": "3+1=?", "options": ["2", "4", "5", "6"], "a": "B"},
        {"q": "5-2=?", "options": ["2", "3", "4", "1"], "a": "B"},
        {"q": "6/2=?", "options": ["2", "3", "4", "5"], "a": "B"},
        {"q": "7-3=?", "options": ["3", "4", "5", "2"], "a": "B"},
    ],
    "medium": [
        {"q": "5*2=?", "options": ["10", "8", "6", "12"], "a": "A"},
        {"q": "10/2=?", "options": ["2", "5", "10", "8"], "a": "B"},
        {"q": "8*3=?", "options": ["24", "20", "18", "21"], "a": "A"},
        {"q": "15-7=?", "options": ["6", "7", "8", "9"], "a": "C"},
        {"q": "9+6=?", "options": ["14", "15", "16", "13"], "a": "B"},
    ],
    "hard": [
        {"q": "12*3=?", "options": ["36", "30", "33", "40"], "a": "A"},
        {"q": "√16=?", "options": ["4", "5", "6", "3"], "a": "A"},
        {"q": "25/5=?", "options": ["5", "6", "4", "3"], "a": "A"},
        {"q": "14+9=?", "options": ["21", "22", "23", "24"], "a": "C"},
        {"q": "18-11=?", "options": ["6", "7", "8", "9"], "a": "B"},
    ]
}

# ===== СТАРТ =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Привет 👋 Выбери действие:", reply_markup=main_kb)

# ===== AI =====
@dp.message_handler(lambda m: m.text == "🤖 AI")
async def ai_mode(message: types.Message):
    user_mode[message.from_user.id] = "ai"
    await message.answer("🤖 Напиши вопрос (рус/қазақша)")

# ===== ТЕСТ =====
@dp.message_handler(lambda m: m.text == "📝 Тест")
async def test_start(message: types.Message):
    await message.answer("Выбери уровень:", reply_markup=level_kb)

@dp.message_handler(lambda m: m.text in ["🟢 Легкий", "🟡 Средний", "🔴 Сложный"])
async def set_level(message: types.Message):
    user_id = message.from_user.id

    if "Легкий" in message.text:
        level = "easy"
    elif "Средний" in message.text:
        level = "medium"
    else:
        level = "hard"

    user_mode[user_id] = "test"
    user_level[user_id] = level
    user_score[user_id] = 0
    user_question[user_id] = 0

    user_test_questions[user_id] = random.sample(
        questions[level],
        min(10, len(questions[level]))
    )

    await send_question(message, user_id)

# ===== ВОПРОС =====
async def send_question(message, user_id):
    q_index = user_question[user_id]
    q = user_test_questions[user_id][q_index]

    text = f"Вопрос {q_index+1}/{len(user_test_questions[user_id])}\n\n{q['q']}\n\n"
    letters = ["A", "B", "C", "D"]

    for i, opt in enumerate(q["options"]):
        text += f"{letters[i]}) {opt}\n"

    await message.answer(text, reply_markup=answer_kb)

# ===== ПРЕМИУМ =====
@dp.message_handler(lambda m: m.text == "💎 Премиум")
async def premium(message: types.Message):
    await message.answer("Kaspi: 87001234567\nНапиши 'оплатил'")

@dp.message_handler(lambda m: m.text.lower() == "оплатил")
async def confirm(message: types.Message):
    premium_users.add(message.from_user.id)
    await message.answer("🔥 Премиум активирован")

# ===== ОБРАБОТКА =====
@dp.message_handler()
async def handle(message: types.Message):
    user_id = message.from_user.id
    text = message.text.upper()

    # === AI ===
    if user_mode.get(user_id) == "ai":
        await bot.send_chat_action(user_id, "typing")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Отвечай на языке пользователя (русский или казахский)"},
                {"role": "user", "content": message.text}
            ]
        )

        await message.answer(response.choices[0].message.content)
        return

    # === TEST ===
    if user_mode.get(user_id) == "test":
        q_index = user_question[user_id]
        q = user_test_questions[user_id][q_index]

        if text == q["a"]:
            user_score[user_id] += 1
            await message.answer("✅ Дұрыс / Верно")
        else:
            await message.answer(f"❌ Қате / Неверно\nПравильный: {q['a']}")

        user_question[user_id] += 1

        if user_question[user_id] >= len(user_test_questions[user_id]):
            score = user_score[user_id]
            total = len(user_test_questions[user_id])
            percent = int((score / total) * 100)

            await message.answer(
                f"🎉 Тест аяқталды\nБаллы: {score}/{total}\nРезультат: {percent}%"
            )

            user_mode[user_id] = "menu"
            return

        await send_question(message, user_id)
        return

    await message.answer("Выбери кнопку 👇", reply_markup=main_kb)

# ===== ЗАПУСК =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
