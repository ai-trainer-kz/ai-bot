import os
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
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
def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Начать обучение")
    kb.add("💰 Купить доступ", "📊 Статус")
    kb.add("🌐 Язык")
    kb.add("👑 Админ")
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

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📋 Пользователи")
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
            "wrong": 0,
            "paid": False,
            "created_at": datetime.now()
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

# ===== GPT PROMPT =====
def system_prompt(subject, level, lang):
    if lang == "kz":
        return f"""
Сен — ҰБТ мұғалімі ({subject}).

Оқушы жауап берген соң:
1. Дұрыс/бұрыс айт
2. Дұрыс жауап
3. Қысқа түсініктеме
4. Келесі сұрақ

Формат:
A) B) C) D)

Деңгей: {level}
"""
    else:
        return f"""
Ты — преподаватель ЕНТ ({subject}).

После ответа:
1. Правильно/неправильно
2. Правильный ответ
3. Короткое объяснение
4. Следующий вопрос

Формат:
A) B) C) D)

Уровень: {level}
"""

def ask_gpt(u, user_text=None):
    level = adapt_level(u)

    messages = [
        {"role": "system", "content": system_prompt(u["subject"], level, u["lang"])}
    ]

    messages += u["history"][-10:]

    if not user_text:
        messages.append({"role": "user", "content": "Начни тест"})
    else:
        messages.append({"role": "user", "content": user_text})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.6,
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
    await message.answer("🤖 AI ЕНТ Тренер", reply_markup=main_kb())

# ===== НАЗАД =====
@dp.message_handler(lambda m: "Назад" in (m.text or ""))
async def back(message: types.Message):
    ensure_user(message.from_user.id)
    users[message.from_user.id]["step"] = "idle"
    await message.answer("Главное меню", reply_markup=main_kb())

# ===== ЯЗЫК =====
@dp.message_handler(lambda m: m.text == "🌐 Язык")
async def choose_lang(message: types.Message):
    await message.answer("Выбери язык", reply_markup=lang_kb())

@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def set_lang(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[message.from_user.id]

    u["lang"] = "kz" if "Қазақша" in message.text else "ru"

    text = "Тіл өзгертілді 🇰🇿" if u["lang"] == "kz" else "Язык изменён 🇷🇺"
    await message.answer(text, reply_markup=main_kb())

# ===== ОБУЧЕНИЕ =====
@dp.message_handler(lambda m: m.text == "📚 Начать обучение")
async def choose_subject(message: types.Message):
    ensure_user(message.from_user.id)
    users[message.from_user.id]["step"] = "subject"
    await message.answer("Выбери предмет", reply_markup=subject_kb())

@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["Математика","История","Биология","Химия"]))
async def choose_level(message: types.Message):
    u = users[message.from_user.id]
    u["subject"] = message.text.split(" ",1)[-1]
    u["step"] = "level"
    await message.answer("Выбери уровень", reply_markup=level_kb())

@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["База","Средний","Сложный"]))
async def start_ai(message: types.Message):
    u = users[message.from_user.id]
    u["level"] = message.text
    u["step"] = "ai"
    u["history"] = []

    if not can_use(u):
        await message.answer(f"❌ Лимит\nKaspi: {KASPI}", reply_markup=pay_kb())
        return

    text = ask_gpt(u)
    await message.answer(text, reply_markup=answer_kb())

@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer_buttons(message: types.Message):
    u = users[message.from_user.id]

    if u["step"] != "ai":
        return

    if not has_access(u):
        u["messages_used"] += 1

    text = ask_gpt(u, message.text)
    await message.answer(text, reply_markup=answer_kb())

# ===== СТАТУС =====
@dp.message_handler(lambda m: m.text == "📊 Статус")
async def status(message: types.Message):
    u = users[message.from_user.id]
    total = u["correct"] + u["wrong"]
    percent = int((u["correct"] / total) * 100) if total else 0

    await message.answer(f"📊\n✅ {u['correct']}\n❌ {u['wrong']}\n📈 {percent}%")

# ===== ОПЛАТА =====
@dp.message_handler(lambda m: m.text == "💰 Купить доступ")
async def pay(message: types.Message):
    await message.answer(
        f"Kaspi: {KASPI}\n7 дней — {PRICE_7}\n30 дней — {PRICE_30}",
        reply_markup=pay_kb()
    )

@dp.message_handler(lambda m: m.text == "💰 Оплатил")
async def paid(message: types.Message):
    user = message.from_user

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("⚡ 7 дней", callback_data=f"give7_{user.id}"),
        InlineKeyboardButton("🚀 30 дней", callback_data=f"give30_{user.id}")
    )

    text = (
        f"💰 Новый платеж!\n\n"
        f"👤 @{user.username}\n"
        f"🆔 ID: {user.id}\n"
        f"📛 Имя: {user.first_name}"
    )

    await bot.send_message(ADMIN_ID, text, reply_markup=kb)
    await message.answer("⏳ Ждите подтверждения")

# ===== CALLBACK =====
@dp.callback_query_handler(lambda c: c.data.startswith("give7_"))
async def give7_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    uid = int(callback.data.split("_")[1])
    ensure_user(uid)

    users[uid]["premium_until"] = datetime.now() + timedelta(days=7)
    users[uid]["paid"] = True

    await bot.send_message(uid, "🎉 Вам выдан доступ на 7 дней!")
    await callback.message.edit_text("✅ Выдано 7 дней")

@dp.callback_query_handler(lambda c: c.data.startswith("give30_"))
async def give30_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    uid = int(callback.data.split("_")[1])
    ensure_user(uid)

    users[uid]["premium_until"] = datetime.now() + timedelta(days=30)
    users[uid]["paid"] = True

    await bot.send_message(uid, "🎉 Вам выдан доступ на 30 дней!")
    await callback.message.edit_text("✅ Выдано 30 дней")

# ===== АДМИН =====
@dp.message_handler(lambda m: m.text == "👑 Админ")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Админ панель", reply_markup=admin_kb())

@dp.message_handler(lambda m: m.text == "📋 Пользователи")
async def users_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    total = len(users)
    paid = sum(1 for u in users.values() if u["paid"])
    active = sum(1 for u in users.values() if u["premium_until"] and datetime.now() < u["premium_until"])

    text = f"📊\n👥 {total}\n💰 {paid}\n🔥 {active}\n\n"

    for uid, u in list(users.items())[-10:]:
        text += f"{'💰' if u['paid'] else '🆓'} {uid}\n"

    await message.answer(text)

# ===== ЗАПУСК =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
