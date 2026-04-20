import os
import json
import re

def clean_text(text):
    text = re.sub(r"\\\(|\\\)", "", text)
    text = re.sub(r"\\frac\{(.*?)\}\{(.*?)\}", r"\1/\2", text)
    text = text.replace("\\", "")
    return text
    
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

client = OpenAI(api_key=OPENAI_API_KEY)

ADMIN_ID = 8398266271

USERS_FILE = "users.json"
user_data = {}

# ===== USERS =====
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

# ===== KEYBOARDS =====
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "📊 Статистика")
    kb.add("🏆 Топ", "💳 Оплата")
    return kb

def subjects_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "Физика")
    kb.add("Биология", "Химия")
    kb.add("История")
    kb.add("⬅️ Назад")
    return kb

def answers_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B")
    kb.add("C", "D")
    kb.add("⬅️ Назад")
    return kb

# ===== AI =====
async def generate_question(subject):
    prompt = f"""
Ты строгий генератор тестов для ЕНТ.

Предмет: {subject}

Сгенерируй 1 вопрос.

Формат строго:
Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A/B/C/D
Объяснение: ...
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

async def generate_explanation(question):
    prompt = f"""
Объясни решение задачи.

Вопрос:
{question}

Дай краткое и понятное объяснение.
НЕ указывай букву ответа.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def parse_question(text):
    correct = re.search(r"Ответ:\s*([A-D])", text)
    explanation = re.search(r"Объяснение:\s*(.*)", text)

    return {
        "text": text,
        "correct": correct.group(1) if correct else None,
        "explanation": explanation.group(1) if explanation else ""
    }

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("👋 Добро пожаловать!", reply_markup=main_menu())

# ===== MENU =====
@dp.message_handler(lambda m: m.text == "📚 Предметы")
async def subjects(message: types.Message):
    await message.answer("Выбери предмет", reply_markup=subjects_kb())

@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def stats(message: types.Message):
    users = load_users()
    user_id = str(message.from_user.id)

    if user_id not in users:
        await message.answer("Нет данных")
        return

    correct = users[user_id]["correct"]
    wrong = users[user_id]["wrong"]
    total = correct + wrong

    accuracy = round((correct / total) * 100, 1) if total > 0 else 0

    await message.answer(
        f"📊 Твоя статистика:\n\n"
        f"✅ Правильно: {correct}\n"
        f"❌ Ошибки: {wrong}\n"
        f"📚 Всего: {total}\n"
        f"🎯 Точность: {accuracy}%"
    )

@dp.message_handler(lambda m: m.text and m.text.strip().lower() in ["математика", "физика", "биология", "химия", "история"])
async def subject_handler(message: types.Message):
    await send_question(message, message.text)

# ===== QUESTION =====
async def send_question(message, subject):
    user_id = str(message.from_user.id)
    users = load_users()

    users.setdefault(user_id, {"used": 0, "expire": ""})

    if users[user_id]["expire"]:
        expire_date = datetime.strptime(users[user_id]["expire"], "%Y-%m-%d")
        if expire_date <= datetime.now():
            users[user_id]["expire"] = ""

    if not users[user_id]["expire"]:
        if users[user_id]["used"] >= 10:
            await message.answer("💳 Лимит закончился. Оплати доступ.")
            return

    users[user_id]["used"] += 1
    save_users(users)

    msg = await message.answer("⏳ Генерирую вопрос...")

    raw = await generate_question(subject)
    data = parse_question(raw)

    await msg.delete()

    clean_text = re.sub(r"Ответ:.*", "", data["text"], flags=re.DOTALL)
    clean_text = re.sub(r"Объяснение:.*", "", clean_text, flags=re.DOTALL)
    clean_text = clean_text.replace("\\(", "").replace("\\)", "")

    user_data[user_id] = {
        "correct": data["correct"],
        "explanation": data["explanation"],
        "question": clean_text,
        "subject": subject
    }

    await message.answer(clean_text.strip(), reply_markup=answers_kb())

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def check_answer(message: types.Message):
    user_id = str(message.from_user.id)
    user_answer = message.text.upper()

    data = user_data.get(user_id, {})
    correct = data.get("correct")
    question = data.get("question", "")
    explanation = data.get("explanation", "")

    # если нет объяснения — генерим
    if not explanation:
        explanation = await generate_explanation(question, correct)
        if not explanation:
            explanation = "📄 Объяснение временно недоступно"

    # очищаем текст
    explanation = clean_text(explanation)

    # ===== СТАТИСТИКА =====
    users = load_users()

    users.setdefault(user_id, {
        "name": message.from_user.full_name,
        "correct": 0,
        "wrong": 0
    })

    # ===== ПРОВЕРКА ОТВЕТА =====
    if user_answer == correct:
        await message.answer("✅ Правильно!")
        users[user_id]["correct"] += 1
    else:
        await message.answer(f"❌ Неправильно\nПравильный ответ: {correct}")
        users[user_id]["wrong"] += 1

    save_users(users)

    # ===== ОБЪЯСНЕНИЕ =====
    await message.answer(
        f"📖 {explanation}\n\nПравильный ответ: {correct}"
    )

    # следующий вопрос
    await send_question(message, data.get("subject", "Математика"))
# ===== BACK =====
@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def back(message: types.Message):
    await message.answer("Меню", reply_markup=main_menu())

# ===== PAYMENT =====
@dp.message_handler(lambda m: m.text == "💳 Оплата")
async def payment(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Я оплатил")
    kb.add("⬅️ Назад")

    await message.answer(
        "💳 Оплата:\n\n"
        "7 дней — 5000₸\n"
        "30 дней — 10000₸\n\n"
        "Kaspi: 4400430352720152\n"
        "Имя: Bauyrzhan\n\n"
        "После оплаты нажми кнопку ниже",
        reply_markup=kb
    )

@dp.message_handler(lambda m: m.text.lower() == "✅ я оплатил")
async def paid(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "-"
    name = message.from_user.full_name

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ 7 дней", callback_data=f"give_7_{user_id}"),
        InlineKeyboardButton("✅ 30 дней", callback_data=f"give_30_{user_id}")
    )
    kb.add(InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{user_id}"))

    text = (
        f"💰 Новая оплата!\n\n"
        f"👤 {name}\n"
        f"📩 @{username}\n"
        f"🆔 {user_id}"
    )

    await bot.send_message(ADMIN_ID, text, reply_markup=kb)
    await message.answer("✅ Заявка отправлена админу")

# ===== ADMIN =====
@dp.callback_query_handler(lambda c: c.data.startswith(("give_", "deny_")))
async def process_callback(callback_query: types.CallbackQuery):
    data = callback_query.data
    user_id = int(data.split("_")[-1])

    if data.startswith("deny"):
        await bot.send_message(user_id, "❌ Платеж отклонён")
        return

    days = 7 if "7" in data else 30

    users = load_users()
    expire = datetime.now() + timedelta(days=days)

    users.setdefault(str(user_id), {})
    users[str(user_id)]["expire"] = expire.strftime("%Y-%m-%d")
    save_users(users)

    await bot.send_message(user_id, f"✅ Доступ выдан на {days} дней")

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
