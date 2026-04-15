import os
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 8398266271

FREE_MESSAGES = 10

PRICE_7 = "5000 тг"
PRICE_30 = "10000 тг"
KASPI = "4400430352720152"

MODEL = "gpt-4o-mini"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

users = {}

# ===== КНОПКИ =====
def main_kb(user_id=None):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Начать обучение")
    kb.add("💰 Купить доступ", "📊 Статус")
    kb.add("🌐 Язык")

    if user_id == ADMIN_ID:
        kb.add("👑 Админ")

    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Дать 7 дней", "➕ Дать 30 дней")
    kb.add("📋 Пользователи")
    kb.add("⬅️ Назад")
    return kb

def subject_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📐 Математика", "📜 История")
    kb.add("🧬 Биология", "🧪 Химия")
    kb.add("⬅️ Назад")
    return kb

def level_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 База", "🟡 Средний", "🔴 Сложный")
    kb.add("⬅️ Назад")
    return kb

def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    kb.add("⬅️ Назад")
    return kb

def lang_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")
    kb.add("⬅️ Назад")
    return kb

def pay_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 Оплатил")
    kb.add("⬅️ Назад")
    return kb

# ===== УТИЛИТЫ =====
def ensure_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "step": "idle",
            "subject": None,
            "level": "Средний",
            "lang": "ru",
            "messages_used": 0,
            "premium_until": None,
            "history": [],
            "correct": 0,
            "wrong": 0
        }

def has_access(u):
    return u["premium_until"] and datetime.now() < u["premium_until"]

def can_use(u):
    return has_access(u) or u["messages_used"] < FREE_MESSAGES

def adapt_level(u):
    if u["correct"] >= 3:
        return "Сложный"
    elif u["wrong"] >= 3:
        return "База"
    return "Средний"

# ===== GPT =====
def system_prompt(subject, level, lang):
    if lang == "kz":
        return f"""
Сен — ҰБТ мұғалімісің: {subject}

Жауаптан кейін:
- дұрыс/бұрыс айт
- дұрыс жауап
- түсіндіру
- келесі сұрақ

A) B) C) D)

Деңгей: {level}
"""
    else:
        return f"""
Ты — преподаватель ЕНТ: {subject}

После ответа:
- правильно/неправильно
- правильный ответ
- объяснение
- следующий вопрос

A) B) C) D)

Уровень: {level}
"""

def ask_gpt(u, user_text=None):
    messages = [
        {"role": "system", "content": system_prompt(u["subject"], adapt_level(u), u["lang"])}
    ]

    messages += u["history"][-10:]

    if not user_text:
        messages.append({"role": "user", "content": "Начни"})
    else:
        messages.append({"role": "user", "content": user_text})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages
    )

    answer = resp.choices[0].message.content

    if user_text:
        u["history"].append({"role": "user", "content": user_text})
    u["history"].append({"role": "assistant", "content": answer})

    return answer

# ===== СТАРТ =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    await message.answer("🤖 AI ЕНТ Тренер", reply_markup=main_kb(message.from_user.id))

# ===== НАЗАД =====
@dp.message_handler(lambda m: "Назад" in (m.text or ""))
async def back(message: types.Message):
    ensure_user(message.from_user.id)
    users[message.from_user.id]["step"] = "idle"
    await message.answer("Главное меню", reply_markup=main_kb(message.from_user.id))

# ===== АДМИН =====
@dp.message_handler(lambda m: m.text == "👑 Админ")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Админ панель", reply_markup=admin_kb())

@dp.message_handler(lambda m: m.text in ["➕ Дать 7 дней", "➕ Дать 30 дней"])
async def admin_choose(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    users[message.from_user.id]["step"] = message.text
    await message.answer("Отправь ID пользователя")

@dp.message_handler(lambda m: users.get(m.from_user.id, {}).get("step") in ["➕ Дать 7 дней", "➕ Дать 30 дней"])
async def admin_give(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        uid = int(message.text)
    except:
        await message.answer("Нужен ID")
        return

    ensure_user(uid)

    if users[message.from_user.id]["step"] == "➕ Дать 7 дней":
        users[uid]["premium_until"] = datetime.now() + timedelta(days=7)
        await message.answer("✅ Выдано 7 дней")
    else:
        users[uid]["premium_until"] = datetime.now() + timedelta(days=30)
        await message.answer("✅ Выдано 30 дней")

# ===== ОПЛАТА =====
@dp.message_handler(lambda m: m.text == "💰 Купить доступ")
async def pay(message: types.Message):
    await message.answer(
        f"💳 Kaspi: {KASPI}\n\n7 дней — {PRICE_7}\n30 дней — {PRICE_30}\n\nПосле оплаты нажми 'Оплатил'",
        reply_markup=pay_kb()
    )

@dp.message_handler(lambda m: m.text == "💰 Оплатил")
async def paid(message: types.Message):
    username = message.from_user.username
    uid = message.from_user.id

    await bot.send_message(
        ADMIN_ID,
        f"💰 Оплата!\nID: {uid}\nUsername: @{username}"
    )

    await message.answer("⏳ Ждите подтверждения")

# ===== ОБУЧЕНИЕ =====
@dp.message_handler(lambda m: m.text == "📚 Начать обучение")
async def subject(message: types.Message):
    ensure_user(message.from_user.id)
    users[message.from_user.id]["step"] = "subject"
    await message.answer("Выбери предмет", reply_markup=subject_kb())

@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["Математика","История","Биология","Химия"]))
async def level(message: types.Message):
    u = users[message.from_user.id]
    u["subject"] = message.text.split(" ",1)[-1]
    u["step"] = "level"
    await message.answer("Выбери уровень", reply_markup=level_kb())

@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["База","Средний","Сложный"]))
async def start_ai(message: types.Message):
    u = users[message.from_user.id]
    u["step"] = "ai"
    u["history"] = []

    text = ask_gpt(u)
    await message.answer(text, reply_markup=answer_kb())

@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = users[message.from_user.id]

    if u["step"] != "ai":
        return

    text = ask_gpt(u, message.text)
    await message.answer(text, reply_markup=answer_kb())

# ===== СТАТУС =====
@dp.message_handler(lambda m: m.text == "📊 Статус")
async def status(message: types.Message):
    u = users[message.from_user.id]
    await message.answer(f"✅ {u['correct']} ❌ {u['wrong']}")

# ===== ЯЗЫК =====
@dp.message_handler(lambda m: m.text == "🌐 Язык")
async def lang(message: types.Message):
    await message.answer("Выбери язык", reply_markup=lang_kb())

@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def set_lang(message: types.Message):
    u = users[message.from_user.id]
    u["lang"] = "kz" if "Қазақша" in message.text else "ru"
    await message.answer("OK", reply_markup=main_kb(message.from_user.id))

# ===== ЗАПУСК =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
