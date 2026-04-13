import logging
import openai
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

# ====== ВСТАВЬ СВОИ КЛЮЧИ ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
openai.api_key = "ТВОЙ_OPENAI_KEY"

# ====== ЛОГИ ======
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ====== ПАМЯТЬ ПОЛЬЗОВАТЕЛЯ ======
users = {}

# ====== КНОПКИ ======
start_kb = ReplyKeyboardMarkup(resize_keyboard=True)
start_kb.add(KeyboardButton("🚀 Начать"))

subjects_kb = ReplyKeyboardMarkup(resize_keyboard=True)
subjects_kb.add("📐 Математика", "📜 История")

levels_kb = ReplyKeyboardMarkup(resize_keyboard=True)
levels_kb.add("🟢 Лёгкий", "🟡 Средний", "🔴 Сложный")

# ====== PROMPT (СЕРДЦЕ БОТА) ======
SYSTEM_PROMPT = """
Ты — AI-тренер как Duolingo.

Правила:
1. Один вопрос за раз.
2. Жди ответ пользователя.
3. После ответа:
   - Правильно → "Правильно! 👍"
   - Неправильно → "Неправильно. Правильный ответ: ..."
4. НЕ объясняй подробно!
5. Коротко! (1-2 предложения)
6. После ответа всегда:
   "Следующий вопрос? 🔥"
7. Не повторяй вопросы.
8. Учитывай уровень сложности.
9. Если пользователь не ответил:
   "Попробуй ответить выше 👆"
"""

# ====== СТАРТ ======
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    users[msg.from_user.id] = {}
    await msg.answer("Привет! Я твой AI-тренер 💪", reply_markup=start_kb)

# ====== НАЧАТЬ ======
@dp.message_handler(lambda msg: msg.text == "🚀 Начать")
async def choose_subject(msg: types.Message):
    await msg.answer("Выбери предмет:", reply_markup=subjects_kb)

# ====== ВЫБОР ПРЕДМЕТА ======
@dp.message_handler(lambda msg: msg.text in ["📐 Математика", "📜 История"])
async def choose_level(msg: types.Message):
    users[msg.from_user.id]["subject"] = msg.text
    await msg.answer("Выбери уровень:", reply_markup=levels_kb)

# ====== ВЫБОР УРОВНЯ ======
@dp.message_handler(lambda msg: msg.text in ["🟢 Лёгкий", "🟡 Средний", "🔴 Сложный"])
async def start_training(msg: types.Message):
    user_id = msg.from_user.id
    users[user_id]["level"] = msg.text

    subject = users[user_id]["subject"]
    level = users[user_id]["level"]

    prompt = f"""
Ты задаёшь первый вопрос по теме: {subject}
Уровень: {level}

Задай короткий вопрос.
"""

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    question = response.choices[0].message.content
    users[user_id]["last_question"] = question

    await msg.answer(question)

# ====== ОБРАБОТКА ОТВЕТОВ ======
@dp.message_handler()
async def handle_answer(msg: types.Message):
    user_id = msg.from_user.id

    if user_id not in users or "last_question" not in users[user_id]:
        await msg.answer("Нажми «Начать» 🚀")
        return

    question = users[user_id]["last_question"]
    subject = users[user_id]["subject"]
    level = users[user_id]["level"]

    prompt = f"""
Вопрос: {question}
Ответ пользователя: {msg.text}

Проверь ответ.
Потом задай новый вопрос по теме: {subject}, уровень: {level}
"""

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    answer = response.choices[0].message.content
    users[user_id]["last_question"] = answer

    await msg.answer(answer)

# ====== ЗАПУСК ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
