import logging
import os
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
premium_users = set()

# ===== КНОПКИ =====
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add(KeyboardButton("🤖 AI"))
main_kb.add(KeyboardButton("📝 Тест"))
main_kb.add(KeyboardButton("💎 Премиум"))

level_kb = ReplyKeyboardMarkup(resize_keyboard=True)
level_kb.add("🟢 Легкий", "🟡 Средний", "🔴 Сложный")

# ===== ВОПРОСЫ =====
questions = {
    "easy": [
        {"q": "2+2=?", "options": ["3", "4", "5"], "a": "4"},
        {"q": "3+1=?", "options": ["2", "4", "5"], "a": "4"},
    ],
    "medium": [
        {"q": "5*2=?", "options": ["10", "8", "6"], "a": "10"},
        {"q": "10/2=?", "options": ["2", "5", "10"], "a": "5"},
    ],
    "hard": [
        {"q": "12*3=?", "options": ["36", "30", "33"], "a": "36"},
        {"q": "√16=?", "options": ["4", "5", "6"], "a": "4"},
    ]
}

# ===== СТАРТ =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Привет 👋\nВыбери действие:", reply_markup=main_kb)

# ===== AI =====
@dp.message_handler(lambda m: m.text == "🤖 AI")
async def ai_mode(message: types.Message):
    user_mode[message.from_user.id] = "ai"
    await message.answer("🤖 AI режим включен. Пиши вопрос")

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

    q = questions[level][0]
    await message.answer(f"{q['q']}\n{q['options']}")

# ===== ПРЕМИУМ =====
@dp.message_handler(lambda m: m.text == "💎 Премиум")
async def premium(message: types.Message):
    await message.answer(
        "💎 Премиум доступ\n\nKaspi: 87001234567\nПосле оплаты напиши 'оплатил'"
    )

@dp.message_handler(lambda m: m.text.lower() == "оплатил")
async def confirm_payment(message: types.Message):
    premium_users.add(message.from_user.id)
    await message.answer("🔥 Премиум активирован!")

# ===== ОБРАБОТКА =====
@dp.message_handler()
async def handle(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    # AI
    if user_mode.get(user_id) == "ai":
        await bot.send_chat_action(user_id, "typing")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Сен ЕНТ бойынша көмекшісің"},
                {"role": "user", "content": text}
            ]
        )

        await message.answer(response.choices[0].message.content)
        return

    # TEST
    if user_mode.get(user_id) == "test":
        level = user_level[user_id]
        q_index = user_question[user_id]
        q = questions[level][q_index]

        if text == q["a"]:
            user_score[user_id] += 1
            await message.answer("✅ Дұрыс!")
        else:
            await message.answer(f"❌ Қате! Жауап: {q['a']}")

        user_question[user_id] += 1

        if user_question[user_id] >= len(questions[level]):
            await message.answer(f"Тест аяқталды 🎉\nБалл: {user_score[user_id]}")
            user_mode[user_id] = "menu"
            await message.answer("Выбери дальше:", reply_markup=main_kb)
            return

        next_q = questions[level][user_question[user_id]]
        await message.answer(f"{next_q['q']}\n{next_q['options']}")
        return

    await message.answer("Выбери кнопку 👇", reply_markup=main_kb)

# ===== ЗАПУСК =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
