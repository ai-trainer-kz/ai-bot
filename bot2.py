import os
import logging
import json
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

# ===== 💾 СОХРАНЕНИЕ =====
def save_users():
    data = {}
    for uid, u in users.items():
        data[uid] = u.copy()
        if u["premium_until"]:
            data[uid]["premium_until"] = u["premium_until"].isoformat()
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_users():
    global users
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            users = data

            for uid in users:
                if users[uid]["premium_until"]:
                    users[uid]["premium_until"] = datetime.fromisoformat(users[uid]["premium_until"])
    except:
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
            "created_at": datetime.now().isoformat()
        }
        save_users()

def has_access(u):
    return u["premium_until"] and datetime.now() < u["premium_until"]

def can_use(u):
    return has_access(u) or u["messages_used"] < FREE_MESSAGES

# ===== GPT =====
def system_prompt(subject, level, lang):
    if lang == "kz":
        return f"""
Сен ҰБТ мұғалімі ({subject}). Деңгей: {level}.

ТЕК тест жаса.

МАЗМҰН:
- ТЕК 1 сұрақ
- 4 жауап нұсқасы

ТЫЙЫМ:
- LaTeX қолданба

ФОРМАТ:
Сұрақ:
...
A) ...
B) ...
C) ...
D) ...

ДҰРЫС ЖАУАП:
A / B / C / D

ЕРЕЖЕ:
- Алдымен тек сұрақ бер
- Пайдаланушы жауап бергеннен кейін:
    - Дұрыс па / Қате екенін айт
    - Қысқа түсіндірме бер
"""
    return f"""
Ты преподаватель ЕНТ ({subject}). Уровень: {level}.

СОЗДАЙ ТОЛЬКО ТЕСТ.

ТРЕБОВАНИЯ:
- Только 1 вопрос
- 4 варианта ответа

ЗАПРЕЩЕНО:
- НЕ используй LaTeX (\( \), \[ \])

ФОРМАТ:
Вопрос:
...
A) ...
B) ...
C) ...
D) ...

Правильный ответ:
A / B / C / D

ПРАВИЛА:
- Сначала давай только вопрос
- После ответа пользователя:
    - Скажи правильно или нет
    - Дай короткое объяснение
"""
def ask_gpt(u, user_text=None):
    messages = [{"role": "system", "content": system_prompt(u["subject"], u["level"], u["lang"])}]
    messages += u["history"][-10:]

    if user_text:
        messages.append({"role": "user", "content": user_text})
    else:
        messages.append({"role": "user", "content": "Начни тест"})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )

    answer = resp.choices[0].message.content

    # чистка текста
    for s in ["\\(", "\\)", "\\[", "\\]", "**"]:
        answer = answer.replace(s, "")

    # замена мат. символов
    answer = answer.replace("\\times", "×")

    if user_text:
        u["history"].append({"role": "user", "content": user_text})
    u["history"].append({"role": "assistant", "content": answer})

    save_users()
    return answer

# ===== СТАРТ =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    await message.answer("🤖 AI ЕНТ Тренер", reply_markup=main_kb(message.from_user.id))

# ===== НАЗАД (FIX) =====
@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def back(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[message.from_user.id]

    u["step"] = "idle"
    u["history"] = []
    u["correct"] = 0
    u["wrong"] = 0
    u["subject"] = None

    save_users()

    await message.answer("Главное меню", reply_markup=main_kb(message.from_user.id))

# ===== ЯЗЫК (FIX) =====
@dp.message_handler(lambda m: m.text == "🌐 Язык")
async def choose_lang(message: types.Message):
    await message.answer("Выбери язык", reply_markup=lang_kb())

@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def set_lang(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[message.from_user.id]

    u["lang"] = "kz" if "Қазақша" in message.text else "ru"
    save_users()

    await message.answer("Язык обновлен", reply_markup=main_kb(message.from_user.id))

# ===== ОБУЧЕНИЕ =====
@dp.message_handler(lambda m: m.text == "📚 Начать обучение")
async def choose_subject(message: types.Message):
    ensure_user(message.from_user.id)
    users[message.from_user.id]["step"] = "subject"
    save_users()
    await message.answer("Выбери предмет", reply_markup=subject_kb())

@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["Математика","История","Биология","Химия"]))
async def choose_level(message: types.Message):
    u = users[message.from_user.id]
    u["subject"] = message.text
    u["step"] = "level"
    save_users()
    await message.answer("Выбери уровень", reply_markup=level_kb())

@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["База","Средний","Сложный"]))
async def start_ai(message: types.Message):
    u = users[message.from_user.id]
    u["level"] = message.text
    u["step"] = "ai"
    u["history"] = []
    save_users()

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

    save_users()
    text = ask_gpt(u, message.text)
    await message.answer(text, reply_markup=answer_kb())

# ===== ОПЛАТА =====
@dp.message_handler(lambda m: m.text == "💰 Купить доступ")
async def pay(message: types.Message):
    await message.answer(f"Kaspi: {KASPI}\n7 дней — {PRICE_7}\n30 дней — {PRICE_30}", reply_markup=pay_kb())

@dp.message_handler(lambda m: m.text == "💰 Оплатил")
async def paid(message: types.Message):
    user = message.from_user

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("⚡ 7 дней", callback_data=f"give7_{user.id}"),
        InlineKeyboardButton("🚀 30 дней", callback_data=f"give30_{user.id}")
    )

    await bot.send_message(
        ADMIN_ID,
        f"💰 Новый платеж!\n@{user.username}\nID: {user.id}",
        reply_markup=kb
    )

    await message.answer("⏳ Ждите подтверждения")

# ===== CALLBACK =====
@dp.callback_query_handler(lambda c: c.data.startswith("give7_"))
async def give7(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    uid = int(callback.data.split("_")[1])
    ensure_user(uid)

    users[uid]["premium_until"] = datetime.now() + timedelta(days=7)
    users[uid]["paid"] = True
    save_users()

    await bot.send_message(uid, "🎉 Доступ на 7 дней!")
    await callback.message.edit_text("✅ 7 дней")

@dp.callback_query_handler(lambda c: c.data.startswith("give30_"))
async def give30(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    uid = int(callback.data.split("_")[1])
    ensure_user(uid)

    users[uid]["premium_until"] = datetime.now() + timedelta(days=30)
    users[uid]["paid"] = True
    save_users()

    await bot.send_message(uid, "🎉 Доступ на 30 дней!")
    await callback.message.edit_text("✅ 30 дней")

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

    text = "👥 Пользователи:\n\n"
    for uid in users:
        text += f"{uid}\n"

    await message.answer(text)

# ===== ЗАПУСК =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
