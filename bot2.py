import os
import json
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

ADMIN_ID = 8398266271

# ====== DATA ======
DATA_FILE = "users.json"

def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_data = {}
question_cache = {}

# ====== KEYBOARDS ======
def main_menu(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "📊 Статистика")
    kb.add("🏆 Топ", "💳 Оплата")
    kb.add("🌐 Тіл / Язык")
    return kb

def subjects_kb(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "Физика")
    kb.add("Биология", "Химия")
    kb.add("История", "Тарих")
    kb.add("⬅️ Назад")
    return kb

def difficulty_kb(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Легкий", "🟡 Средний")
    kb.add("🔴 Сложный")
    kb.add("⬅️ Назад")
    return kb

# ====== START ======
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("👋 Добро пожаловать!", reply_markup=main_menu(message.from_user.id))

# ====== SUBJECT ======
@dp.message_handler(lambda m: m.text == "📚 Предметы")
async def subjects(message: types.Message):
    await message.answer("Выбери предмет", reply_markup=subjects_kb(message.from_user.id))

@dp.message_handler(lambda m: m.text.lower() in ["математика","физика","биология","химия","история","тарих"])
async def subject_handler(message: types.Message):
    user_id = str(message.from_user.id)

    user_data.setdefault(user_id, {})
    user_data[user_id]["subject"] = message.text

    await message.answer(
        "Выбери сложность",
        reply_markup=difficulty_kb(user_id)
    )

# ====== DIFFICULTY ======
@dp.message_handler(lambda m: m.text in ["🟢 Легкий", "🟡 Средний", "🔴 Сложный"])
async def difficulty_handler(message: types.Message):
    user_id = str(message.from_user.id)

    users = load_users()
    users.setdefault(user_id, {})

    if "Легкий" in message.text:
        users[user_id]["level"] = "easy"
    elif "Средний" in message.text:
        users[user_id]["level"] = "medium"
    else:
        users[user_id]["level"] = "hard"

    save_users(users)

    subject = user_data.get(user_id, {}).get("subject")

    if not subject:
        subject = "Математика"

    await message.answer("🚀 Начинаем тест...")

    await send_question(message, subject)

# ====== AI QUESTION ======
async def generate_question(subject, level):
    level_text = {
        "easy": "легкий",
        "medium": "средний",
        "hard": "сложный"
    }[level]

    prompt = f"""
Сгенерируй {level_text} тест ЕНТ

Предмет: {subject}

Формат:
Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A/B/C/D
Объяснение: ...
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return r.choices[0].message.content
    except:
        return """Вопрос: 2+2?
A) 3
B) 4
C) 5
D) 6
Ответ: B
Объяснение: 2+2=4"""

# ====== PARSE ======
def parse_question(text):
    lines = text.split("\n")

    question = ""
    options = []
    correct = ""
    explanation = ""

    for line in lines:
        if line.startswith("Вопрос"):
            question = line
        elif line.startswith(("A)", "B)", "C)", "D)")):
            options.append(line)
        elif "Ответ" in line:
            correct = line.split(":")[-1].strip()
        elif "Объяснение" in line:
            explanation = line

    return question, options, correct, explanation

# ====== SEND QUESTION ======
async def send_question(message, subject):
    user_id = str(message.from_user.id)
    users = load_users()

    level = users.get(user_id, {}).get("level", "easy")

    raw = await generate_question(subject, level)
    q, opts, correct, explanation = parse_question(raw)

    user_data[user_id]["correct"] = correct
    user_data[user_id]["explanation"] = explanation
    user_data[user_id]["subject"] = subject

    text = q + "\n" + "\n".join(opts)

    await message.answer(text)

# ====== ANSWER ======
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer_handler(message: types.Message):
    user_id = str(message.from_user.id)

    correct = user_data.get(user_id, {}).get("correct")
    explanation = user_data.get(user_id, {}).get("explanation")
    subject = user_data.get(user_id, {}).get("subject")

    if message.text == correct:
        await message.answer("✅ Правильно")
    else:
        await message.answer(f"❌ Неправильно\nПравильный ответ: {correct}")

    await message.answer(explanation)

    await asyncio.sleep(1)

    await message.answer("➡️ Следующий вопрос...")

    await send_question(message, subject)

# ====== BACK ======
@dp.message_handler(lambda m: m.text == "💳 Оплата")
async def pay(message: types.Message):
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Я оплатил"); kb.add("⬅️ Назад")
    await message.answer("Kaspi: 4400430352720152", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "💳 Оплата")
async def pay(message: types.Message):
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Я оплатил"); kb.add("⬅️ Назад")
    await message.answer("Kaspi: 4400430352720152", reply_markup=kb)

@dp.message_handler(lambda m: "оплатил" in m.text.lower())
async def paid(message: types.Message):
    u=message.from_user

    kb=InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ 7 дней", callback_data=f"give_7_{u.id}"),
        InlineKeyboardButton("✅ 30 дней", callback_data=f"give_30_{u.id}")
    )
    kb.add(InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{u.id}"))

    await bot.send_message(
        ADMIN_ID,
        f"💰 Новая оплата!\n\n👤 {u.full_name}\n📩 @{u.username}\n🆔 {u.id}",
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith("give_"))
async def give(callback_query: types.CallbackQuery):
    uid=int(callback_query.data.split("_")[-1])
    days=7 if "7" in callback_query.data else 30

    users=load_users()
    users.setdefault(str(uid),{})

    expire=datetime.now()+timedelta(days=days)
    users[str(uid)]["expire"]=expire.strftime("%Y-%m-%d")
    users[str(uid)]["used"]=0  # 🔥 сброс лимита

    save_users(users)

    await bot.send_message(uid,f"✅ Доступ на {days} дней")

@dp.callback_query_handler(lambda c: c.data.startswith("deny_"))
async def deny(callback_query: types.CallbackQuery):
    uid=int(callback_query.data.split("_")[-1])
    await bot.send_message(uid,"❌ Оплата отклонена")


# ====== RUN ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
