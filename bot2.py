import os
import json
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
def generate_question(subject):
    prompt = f"""
Сгенерируй 1 тестовый вопрос по предмету {subject} (ЕНТ).

Формат:
Q: ...
A) ...
B) ...
C) ...
D) ...
ANSWER: A
EXPLAIN: ...
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

def parse_question(text):
    lines = text.split("\n")

    q, options, answer, explain = "", [], "", ""

    for line in lines:
        if line.startswith("Q:"):
            q = line.replace("Q:", "").strip()
        elif line.startswith(("A)", "B)", "C)", "D)")):
            options.append(line.strip())
        elif line.startswith("ANSWER:"):
            answer = line.replace("ANSWER:", "").strip()
        elif line.startswith("EXPLAIN:"):
            explain = line.replace("EXPLAIN:", "").strip()

    return q, options, answer, explain

# ========= KEYBOARDS =========
def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "💳 Оплата")
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

# ========= MENU =========
@dp.message_handler(lambda m: m.text == "📚 Предметы")
async def subjects(msg: types.Message):
    await msg.answer("Выбери предмет", reply_markup=subjects_kb())

@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def back(msg: types.Message):
    await msg.answer("Меню", reply_markup=main_kb())

# ========= SUBJECT =========
@dp.message_handler(lambda m: m.text in ["Математика","Физика","Химия","Биология","История"])
async def subject_handler(message: types.Message):

    if not has_access(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return

    subject = message.text

    text = generate_question(subject)
    q, options, answer, explain = parse_question(text)

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B")
    kb.add("C", "D")

    await message.answer(q + "\n\n" + "\n".join(options), reply_markup=kb)

    user_state[message.from_user.id] = {
        "answer": answer,
        "explain": explain,
        "subject": subject
    }

# ========= ANSWER =========
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def check_answer(message: types.Message):

    user = message.from_user.id

    if user not in user_state:
        return

    correct = user_state[user]["answer"]
    explain = user_state[user]["explain"]
    subject = user_state[user]["subject"]

    if message.text == correct:
        await message.answer(f"✅ Правильно!\n\n📖 {explain}")
    else:
        await message.answer(f"❌ Неправильно\nПравильный ответ: {correct}\n\n📖 {explain}")

    users = load_users()
    user = str(message.from_user.id)
    
    used = users.get(user, {}).get("used", 0)
    
    users.setdefault(user, {})
    users[user]["used"] = used + 1
    save_users(users)

    if used + 1 >= FREE_LIMIT and not has_access(message.from_user.id):
    await message.answer("🔒 Бесплатные вопросы закончились\n💳 Купите доступ")
    user_state[message.from_user.id] = {}
    return

    text = generate_question(subject)

    q, options, answer, explain = parse_question(text)

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B")
    kb.add("C", "D")
    kb.add("⬅️ Назад")
    kb.add("🏠 Главное меню")
    await message.answer(q + "\n\n" + "\n".join(options), reply_markup=kb)

    user_state[user] = {
        "answer": answer,
        "explain": explain,
        "subject": subject
    }

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
    kb.add(
        InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{user.id}")
    )

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
