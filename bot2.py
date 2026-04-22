import os
import json
import re
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

ADMIN_ID = 8398266271
USERS_FILE = "users.json"

user_data = {}
user_results = {}

# ===== SESSION =====
def get_user_session(uid):
    uid = str(uid)
    user_results.setdefault(uid, {
        "correct": 0,
        "wrong": 0,
        "mistakes": [],
        "topics": {},
        "total": 0
    })
    return user_results[uid]

# ===== USERS =====
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def get_lang(uid):
    return load_users().get(str(uid), {}).get("lang", "ru")

def t(uid, ru, kz):
    return kz if get_lang(uid) == "kz" else ru

# ===== КНОПКИ =====
def main_menu(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(t(uid,"📚 Предметы","📚 Пәндер"), t(uid,"📊 Статистика","📊 Статистика"))
    kb.add(t(uid,"🏆 Топ","🏆 ТОП"), t(uid,"💳 Оплата","💳 Төлем"))
    kb.add(t(uid,"🧠 Тренажёр","🧠 Тренажёр"), t(uid,"📖 Обучение","📖 Оқу"))
    kb.add("🌐 Тіл / Язык")
    return kb

def answers_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    return kb

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("👋 Добро пожаловать!", reply_markup=main_menu(message.from_user.id))

# ===== ВОПРОС =====
async def send_question(message):
    uid = str(message.from_user.id)

    subject = user_data.get(uid, {}).get("subject", "математика")
    lang = get_lang(uid)

    prompt = f"""
Сделай 1 тестовый вопрос по предмету {subject}.
Язык: {"казахский" if lang=="kz" else "русский"}

Формат:

Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A/B/C/D
Объяснение: ...
"""

    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )

    text = r.choices[0].message.content

    correct = re.search(r"Ответ:\s*([A-D])", text)
    explanation = re.search(r"Объяснение:\s*(.*)", text)

    user_data[uid] = {
        "correct": correct.group(1) if correct else "A",
        "explanation": explanation.group(1) if explanation else "",
        "subject": subject
    }

    q = re.sub(r"Ответ:.*","",text,flags=re.DOTALL)
    q = re.sub(r"Объяснение:.*","",q,flags=re.DOTALL)

    await message.answer(q.strip(), reply_markup=answers_kb())

# ===== ОТВЕТ =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    uid = str(message.from_user.id)
    data = user_data.get(uid)

    if not data:
        return

    users = load_users()
    session = get_user_session(uid)

    users.setdefault(uid, {"correct":0,"wrong":0,"lang":"ru"})
    lang = users[uid]["lang"]

    if message.text == data["correct"]:
        await message.answer("✅ Дұрыс" if lang=="kz" else "✅ Правильно")
        users[uid]["correct"] += 1
        session["correct"] += 1
    else:
        await message.answer(
            f"❌ Қате\nДұрыс жауап: {data['correct']}" if lang=="kz"
            else f"❌ Неправильно\nПравильный ответ: {data['correct']}"
        )
        users[uid]["wrong"] += 1
        session["wrong"] += 1

    session["total"] += 1
    save_users(users)

    if data["explanation"]:
        await message.answer(
            f"📖 Түсіндірме:\n{data['explanation']}" if lang=="kz"
            else f"📖 Объяснение:\n{data['explanation']}"
        )

    await send_question(message)

# ===== ТРЕНАЖЁР =====
@dp.message_handler(lambda m: "Тренаж" in m.text)
async def trainer(message: types.Message):
    await send_question(message)

# ===== ОПЛАТА (НЕ ТРОГАЛ) =====
@dp.message_handler(lambda m: m.text in ["💳 Оплата","💳 Төлем"])
async def pay(message: types.Message):
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Я оплатил"); kb.add("⬅️ Назад")
    await message.answer("Kaspi: 4400430352720152", reply_markup=kb)

@dp.message_handler(lambda m: "оплатил" in m.text.lower())
async def paid(message: types.Message):
    u = message.from_user
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("7 дней", callback_data=f"give_7_{u.id}"),
        InlineKeyboardButton("30 дней", callback_data=f"give_30_{u.id}")
    )
    kb.add(InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{u.id}"))

    await bot.send_message(
        ADMIN_ID,
        f"💰 Оплата\n{u.full_name}\n@{u.username}\n{u.id}",
        reply_markup=kb
    )

# ===== RUN =====
if __name__=="__main__":
    executor.start_polling(dp, skip_updates=True)
