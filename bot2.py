import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from openai import OpenAI

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

client = OpenAI(api_key=OPENAI_API_KEY)

# ====== БАЗА (в памяти) ======
user_mode = {}
user_score = {}
user_question = {}
premium_users = set()

# ====== ВОПРОСЫ (тест) ======
questions = [
    {"question": "2+2=?", "options": ["3", "4", "5"], "answer": "4"},
    {"question": "Столица Казахстана?", "options": ["Алматы", "Астана", "Шымкент"], "answer": "Астана"},
]

# ====== ПРОВЕРКА ПРЕМИУМА ======
def is_premium(user_id):
    return user_id in premium_users

# ====== СТАРТ ======
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Привет 👋\n\nКоманды:\n/ai - ИИ\n/test - тест\n/premium - премиум")

# ====== AI РЕЖИМ ======
@dp.message_handler(commands=['ai'])
async def ai_mode(message: types.Message):
    user_mode[message.from_user.id] = "ai"
    await message.answer("🤖 AI режим включен")

# ====== ТЕСТ ======
@dp.message_handler(commands=['test'])
async def test_mode(message: types.Message):
    user_id = message.from_user.id
    user_mode[user_id] = "test"
    user_score[user_id] = 0
    user_question[user_id] = 0

    q = questions[0]
    await message.answer(f"{q['question']}\n{q['options']}")

# ====== ПРЕМИУМ ======
@dp.message_handler(commands=['premium'])
async def premium(message: types.Message):
    premium_users.add(message.from_user.id)
    await message.answer("🔥 Премиум активирован")

# ====== ОБРАБОТЧИК ======
@dp.message_handler()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    # ==== AI ====
    if user_mode.get(user_id) == "ai":
        await bot.send_chat_action(user_id, "typing")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты помощник по ЕНТ. Отвечай кратко."},
                {"role": "user", "content": text}
            ]
        )

        await message.answer(response.choices[0].message.content)
        return

    # ==== ТЕСТ ====
    if user_mode.get(user_id) == "test":
        q_index = user_question[user_id]
        q = questions[q_index]

        if text == q["answer"]:
            user_score[user_id] += 1
              await message.answer("✅ Верно!")
        else:
              await message.answer(f"❌ Неверно! Ответ: {q['answer']}")

              user_question[user_id] += 1

           if user_question[user_id] >= len(questions):
              await message.answer(f"Тест завершен 🎉\nБаллы: {user_score[user_id]}")
            user_mode[user_id] = "default"
            return

        next_q = questions[user_question[user_id]]
        await message.answer(f"{next_q['question']}\n{next_q['options']}")
        return

    # ==== ПРЕМИУМ ====
    if user_mode.get(user_id) == "premium":
        if not is_premium(user_id):
            await message.answer("❌ Купи премиум")
            return

    await message.answer("Напиши /ai или /test")

# ====== ЗАПУСК ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
