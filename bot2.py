import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ===== LOAD USERS =====
try:
    with open("users.json", "r") as f:
        users = json.load(f)
except:
    users = {}

def save_users():
    with open("users.json", "w") as f:
        json.dump(users, f)


# ===== КНОПКИ =====
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add("📚 Начать обучение")
main_menu.add("💰 Купить доступ", "📊 Статус")
main_menu.add("🌐 Язык")

subjects_kb = ReplyKeyboardMarkup(resize_keyboard=True)
subjects_kb.add("📐 Математика", "🧪 Химия")
subjects_kb.add("🧬 Биология")
subjects_kb.add("⬅️ Назад")

levels_kb = ReplyKeyboardMarkup(resize_keyboard=True)
levels_kb.add("🟢 База", "🔴 Сложно")
levels_kb.add("⬅️ Назад")


# ===== START =====
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    user_id = str(message.from_user.id)

    if user_id not in users:
        users[user_id] = {}

    # 👉 ДОБАВИЛ (инициализация счётчика)
    users[user_id].setdefault("score", 0)
    users[user_id].setdefault("question_count", 0)

    # ✅ ОДНОРАЗОВОЕ ПРИВЕТСТВИЕ
    if not users[user_id].get("seen_welcome"):
        await message.answer(
            "👋 Добро пожаловать в AI ЕНТ Тренер!\n\n"
            "📚 Выбирай предмет\n"
            "🧠 Решай тесты\n"
            "🚀 Готовься к ЕНТ\n"
        )
        users[user_id]["seen_welcome"] = True
        save_users()

    await message.answer("Выбери действие:", reply_markup=main_menu)


# ===== НАЧАТЬ =====
@dp.message_handler(lambda m: m.text == "📚 Начать обучение")
async def choose_subject(message: types.Message):
    await message.answer("Выбери предмет:", reply_markup=subjects_kb)


# ===== НАЗАД =====
@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def go_back(message: types.Message):
    await message.answer("Выбери действие:", reply_markup=main_menu)


# ===== ПРЕДМЕТ =====
@dp.message_handler(lambda m: m.text in ["📐 Математика", "🧪 Химия", "🧬 Биология"])
async def choose_level(message: types.Message):
    user_id = str(message.from_user.id)
    users[user_id]["subject"] = message.text
    save_users()

    await message.answer("Выбери уровень:", reply_markup=levels_kb)


# ===== УРОВЕНЬ =====
@dp.message_handler(lambda m: m.text in ["🟢 База", "🔴 Сложно"])
async def start_test(message: types.Message):
    user_id = str(message.from_user.id)
    subject = users[user_id].get("subject", "Математика")

    # 👉 ДОБАВИЛ (обнуление теста)
    users[user_id]["score"] = 0
    users[user_id]["question_count"] = 0
    save_users()

    prompt = f"Сгенерируй 1 тестовый вопрос по предмету {subject} с 4 вариантами и правильным ответом. Без объяснения."

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.choices[0].message.content

    users[user_id]["last_question"] = text
    save_users()

    await message.answer(f"Вопрос 1/10:\n{text}")


# ===== ОТВЕТ ПОЛЬЗОВАТЕЛЯ =====
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def check_answer(message: types.Message):
    user_id = str(message.from_user.id)
    question = users[user_id].get("last_question", "")

    prompt = f"""
Вопрос:
{question}

Пользователь выбрал: {message.text}

Ответь ТОЛЬКО так:
CORRECT
или
WRONG:X
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    result = response.choices[0].message.content.strip()

    # 👉 ДОБАВИЛ (логика подсчёта)
    users[user_id]["question_count"] += 1

    if "CORRECT" in result:
        users[user_id]["score"] += 1
        await message.answer("✅ Правильно!")
    else:
        correct = result.split(":")[-1]
        await message.answer(f"❌ Неправильно! Правильный ответ: {correct}")

    save_users()

    # 👉 ДОБАВИЛ (финал теста)
    if users[user_id]["question_count"] >= 10:
        score = users[user_id]["score"]
        percent = score * 10

        await message.answer(
            f"📊 Результат:\n\n"
            f"Ты ответил правильно: {score}/10\n"
            f"Готовность к ЕНТ: {percent}%\n\n"
            f"🔥 Хочешь полный доступ?\n"
            f"👉 1000+ вопросов\n"
            f"👉 Все предметы\n"
            f"👉 Без ограничений\n\n"
            f"💰 Купить доступ",
            reply_markup=main_menu
        )
        return

    # следующий вопрос (ТВОЯ ЛОГИКА НЕ ТРОНУТА)
    await start_test(message)


# ===== ЗАПУСК =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
