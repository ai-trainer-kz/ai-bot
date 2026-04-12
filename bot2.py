import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from openai import OpenAI

# === ТОКЕНЫ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

# === БАЗА ===
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    score INTEGER DEFAULT 0,
    premium INTEGER DEFAULT 0
)
""")
conn.commit()

# === ПАМЯТЬ ===
user_mode = {}

# === ПРОВЕРКА ПРЕМИУМА ===
def is_premium(user_id):
    cursor.execute("SELECT premium FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row and row[0] == 1

# === СТАРТ ===
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    user_id = message.from_user.id

    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

    await message.answer("Привет! Выбери режим:\n/test\n/ai")

# === ТЕСТ РЕЖИМ ===
@dp.message_handler(commands=["test"])
async def test_mode(message: types.Message):
    user_id = message.from_user.id

    user_mode[user_id] = {
        "mode": "test",
        "answer": "4"
    }

    await message.answer("Сколько будет 2+2?")

# === AI РЕЖИМ ===
@dp.message_handler(commands=["ai"])
async def ai_mode(message: types.Message):
    user_id = message.from_user.id
    user_mode[user_id] = "ai"

    await message.answer("Задай вопрос")

# === ОСНОВНОЙ ОБРАБОТЧИК ===
@dp.message_handler()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    # ===== ПРОВЕРКА ТЕСТА =====
    if user_id in user_mode and isinstance(user_mode[user_id], dict):
        if user_mode[user_id].get("mode") == "test":
            correct = user_mode[user_id]["answer"]

            if text == correct:
                await message.answer("✅ Правильно!")
            else:
                await message.answer(f"❌ Неправильно. Ответ: {correct}")

            user_mode[user_id] = {}
            return

    await bot.send_chat_action(user_id, "typing")

    # ===== ТЕСТ =====
    if user_id in user_mode and isinstance(user_mode[user_id], dict):
        q = user_mode[user_id]

        if text == q["answer"]:
            await message.answer("✅ Правильно!")
            cursor.execute(
                "UPDATE users SET score = score + 1 WHERE user_id=?",
                (user_id,)
            )
            conn.commit()
        else:
            await message.answer(f"❌ Неправильно. Ответ: {q['answer']}")

        del user_mode[user_id]
        return

    # ===== ИИ =====
    if user_mode.get(user_id) == "ai":
        await bot.send_chat_action(user_id, "typing")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты помощник по ЕНТ. Отвечай кратко и понятно."},
                {"role": "user", "content": text}
            ]
        )

        await message.answer(response.choices[0].message.content)
        return

    # ===== ПРЕМИУМ =====
    if user_mode.get(user_id) == "premium":
        if not is_premium(user_id):
            await message.answer("❌ Купи премиум")
            return

# === ЗАПУСК ===
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
