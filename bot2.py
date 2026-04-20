import os
import json
import random
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from openai import OpenAI

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ADMINS = [8398266271]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

user_state = {}
last_questions = {}

FREE_LIMIT = 10

# ========= DB =========
if not os.path.exists("users.json"):
    with open("users.json", "w") as f:
        json.dump({}, f)

def load_users():
    with open("users.json", "r") as f:
        return json.load(f)

def save_users(data):
    with open("users.json", "w") as f:
        json.dump(data, f, indent=4)

def has_access(user_id):
    users = load_users()

    if str(user_id) not in users:
        return False

    expire = users[str(user_id)].get("expire")

    if not expire:
        return False

    expire_date = datetime.strptime(expire, "%Y-%m-%d")
    return datetime.now() <= expire_date

# ========= AI =========
def generate_question(subject, user_id):
    prompt = f"""
Ты AI-тренер для ЕНТ.

Сгенерируй 1 новый вопрос по предмету {subject}.

Уровень сложности: случайный (легкий / средний / сложный)

Формат строго:
Q: ...
A) ...
B) ...
C) ...
D) ...
ANSWER: A
EXPLAIN: ...
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.2
    )

    return response.choices[0].message.content

def parse_question(text):
    lines = text.split("\n")

    q, options, answer, explain = "", [], "", ""

    for line in lines:
        line = line.strip()

        if line.startswith("Q:"):
            q = line.replace("Q:", "").strip()
        elif line.startswith(("A)", "B)", "C)", "D)")):
            options.append(line)
        elif line.startswith("ANSWER:"):
            answer = line.replace("ANSWER:", "").strip()
        elif line.startswith("EXPLAIN:"):
            explain = line.replace("EXPLAIN:", "").strip()

    return q, options, answer, explain

# ========= KEYBOARDS =========
def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B")
    kb.add("C", "D")
    kb.add("⬅️ Назад")
    return kb

def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "📊 Статистика")
    kb.add("🏆 Топ", "💳 Оплата")
    return kb

def subjects_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "Физика")
    kb.add("Химия", "Биология")
    kb.add("История")
    kb.add("⬅️ Назад")
    return kb

# ========= START =========
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.answer("Меню", reply_markup=main_kb())

# ========= BACK =========
@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def back(msg: types.Message):
    user_state[msg.from_user.id] = {}
    await msg.answer("Меню", reply_markup=main_kb())

# ========= MENU =========
@dp.message_handler(lambda m: m.text == "📚 Предметы")
async def subjects(msg: types.Message):
    await msg.answer("Выбери предмет", reply_markup=subjects_kb())

@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def stats(message: types.Message):
    users = load_users()
    user = str(message.from_user.id)
    used = users.get(user, {}).get("used", 0)
    await message.answer(f"📊 Вы решили {used} вопросов")

@dp.message_handler(lambda m: m.text == "🏆 Топ")
async def top(message: types.Message):
    users = load_users()

    rating = sorted(users.items(), key=lambda x: x[1].get("used", 0), reverse=True)[:5]

    text = "🏆 ТОП пользователей:\n\n"

    for i, (uid, data) in enumerate(rating, 1):
        text += f"{i}. {uid} — {data.get('used', 0)} вопросов\n"

    await message.answer(text)

# ========= SUBJECT =========
@dp.message_handler(lambda message: message.text in [
    "Математика", "Физика", "Биология", "История", "Химия"
])
async def send_question(message, subject):
    user_id = str(message.from_user.id)
    users = load_users()

    users.setdefault(user_id, {"used": 0})

    # проверка лимита
    if users[user_id]["used"] >= 10:
        await message.answer("💳 Лимит закончился. Оплати доступ.")
        return

    # увеличиваем
    users[user_id]["used"] += 1
    save_users(users)

    # дальше генерация вопроса
    raw = await generate_question(subject)
    data = parse_question(raw)

    user_data[user_id] = {
        "correct": data["correct"],
        "explanation": data["explanation"]
    }

    await message.answer(data["text"], reply_markup=answer_kb())

    subject = message.text

    text = generate_question(subject, user_id)
    q, options, answer, explain = parse_question(text)

    if not q or len(options) < 4:
        await message.answer("⚠️ Ошибка генерации")
        return

    user_state[user_id] = {
        "answer": answer,
        "explain": explain,
        "subject": subject
    }

    await message.answer(q + "\n\n" + "\n".join(options), reply_markup=answer_kb())

# ========= ANSWER =========
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def check_answer(message: types.Message):

    user_id = message.from_user.id

    if user_id not in user_state or not user_state[user_id]:
        await message.answer("Сначала выбери предмет")
        return

    correct = user_state[user_id]["answer"]
    explain = user_state[user_id]["explain"]
    subject = user_state[user_id]["subject"]

    if message.text.upper() == correct.upper():
        await message.answer(f"✅ Правильно!\n\n📖 {explain}")
    else:
        await message.answer(f"❌ Неправильно\nОтвет: {correct}\n\n📖 {explain}")

    users = load_users()
    user = str(user_id)

    users.setdefault(user, {})
    users[user]["used"] = users[user].get("used", 0) + 1
    save_users(users)

    used = users[user]["used"]

    if used >= FREE_LIMIT and not has_access(user_id):
        await message.answer("🔒 Лимит достигнут\n💳 Оплатите доступ")
        user_state[user_id] = {}
        return

    # 👉 следующий вопрос
    text = generate_question(subject, user_id)
    q, options, answer, explain = parse_question(text)

    user_state[user_id] = {
        "answer": answer,
        "explain": explain,
        "subject": subject
    }

    await message.answer(q + "\n\n" + "\n".join(options), reply_markup=answer_kb())

# ========= PAYMENT =========
@dp.message_handler(lambda m: m.text == "💳 Оплата")
async def pay(msg: types.Message):

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Я оплатил")
    kb.add("⬅️ Назад")

    await msg.answer(
        "Kaspi: 4400430352720152\n"
        "7 дней — 5000 тг\n"
        "30 дней — 10000 тг",
        reply_markup=kb
    )

@dp.message_handler(lambda m: m.text == "✅ Я оплатил")
async def paid(message: types.Message):

    user = message.from_user
    users = load_users()

    users.setdefault(str(user.id), {})
    users[str(user.id)].setdefault("used", 0)
    save_users(users)

    text = (
        f"💰 Новая заявка!\n\n"
        f"ID: {user.id}\n"
        f"Имя: {user.first_name}\n"
        f"@{user.username if user.username else 'нет'}"
    )

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("7 дней", callback_data=f"give_7_{user.id}"),
        InlineKeyboardButton("30 дней", callback_data=f"give_30_{user.id}")
    )
    kb.add(InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{user.id}"))

    for admin in ADMINS:
        await bot.send_message(admin, text, reply_markup=kb)

    await message.answer("✅ Заявка отправлена")

# ========= ADMIN =========
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

# ========= RUN =========
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
