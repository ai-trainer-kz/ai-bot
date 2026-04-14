import os
import logging
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

DATA_FILE = "users.json"

def load_users():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()
ADMIN_ID = 503301815

FREE_LIMIT = 10

def is_premium(user_id):
    user = users.get(user_id)
    if not user or not user.get("premium"):
        return False

    expires = user.get("expires")
    if not expires:
        return False

    expires_date = datetime.strptime(expires, "%Y-%m-%d")

    if datetime.now() > expires_date:
        user["premium"] = False
        save_users()
        return False

    return True

# ====== КНОПКИ ======
lang_kb = ReplyKeyboardMarkup(resize_keyboard=True)
lang_kb.add("Русский 🇷🇺", "Қазақ 🇰🇿", "English 🇺🇸")

main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("🚀 Начать", "▶️ Тест")
main_kb.add("📊 Профиль", "💰 Купить")

subjects_kb = ReplyKeyboardMarkup(resize_keyboard=True)
subjects_kb.add("Математика", "История")
subjects_kb.add("Биология", "Қазақ тілі")
subjects_kb.add("Физика", "Химия")

level_kb = ReplyKeyboardMarkup(resize_keyboard=True)
level_kb.add("Лёгкий", "Средний", "Сложный")

answers_kb = ReplyKeyboardMarkup(resize_keyboard=True)
answers_kb.add("A", "B", "C", "D")
answers_kb.add("🔙 Назад", "🛑 Завершить")

pay_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
])

# ====== СТАРТ ======
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid] = users.get(uid, {
        "xp": 0,
        "level": 1,
        "streak": 0,
        "lives": 3,
        "lang": "ru",
        "free_used": 0,
        "premium": False,
        "expires": None
    })
    save_users()

    await msg.answer("Выбери язык 🌍", reply_markup=lang_kb)

# ====== ЯЗЫК ======
@dp.message_handler(lambda msg: msg.text in ["Русский 🇷🇺","Қазақ 🇰🇿","English 🇺🇸"])
async def set_lang(msg: types.Message):
    uid = str(msg.from_user.id)

    lang = "ru" if "Русский" in msg.text else "kz" if "Қазақ" in msg.text else "en"

    users[uid]["lang"] = lang
    save_users()

    await msg.answer("Привет! Я AI-тренер 💪", reply_markup=main_kb)

# ====== КУПИТЬ (ИСПРАВЛЕНО) ======
@dp.message_handler(lambda msg: msg.text == "💰 Купить")
async def buy(msg: types.Message):
    text = """
ПОЛНЫЙ ДОСТУП — 10 000 тг / месяц

Что ты получаешь:

Безлимитные задания
Объяснения как у репетитора
Подготовка к экзаменам
24/7 доступ

Оплата (Kaspi / перевод):
4400430352720152

После оплаты отправь чек:
@ai_teacher1_support

После оплаты нажми кнопку ниже
"""
    await msg.answer(text, reply_markup=pay_kb)

# ====== КНОПКА "Я ОПЛАТИЛ" ======
@dp.callback_query_handler(lambda c: c.data == "paid")
async def paid_handler(callback: types.CallbackQuery):
    user = callback.from_user

    text = f"""
Новый платеж!

@{user.username}
ID: {user.id}
Имя: {user.full_name}
"""

    await bot.send_message(ADMIN_ID, text)

    await callback.message.answer("Принял! Отправь чек в поддержку")
    await callback.answer()

# ====== МЕНЮ ======
@dp.message_handler(lambda msg: msg.text in ["🚀 Начать", "▶️ Тест"])
async def menu(msg: types.Message):
    await msg.answer("Выбери предмет 👇", reply_markup=subjects_kb)

# ====== ПРЕДМЕТ ======
@dp.message_handler(lambda msg: msg.text in ["Математика","История","Биология","Қазақ тілі","Физика","Химия"])
async def subject(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["subject"] = msg.text
    save_users()
    await msg.answer("Выбери уровень:", reply_markup=level_kb)

# ====== УРОВЕНЬ ======
@dp.message_handler(lambda msg: msg.text in ["Лёгкий","Средний","Сложный"])
async def level(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["difficulty"] = msg.text
    save_users()
    await send_question(msg)

# ====== ВОПРОС ======
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]

    if not is_premium(uid) and user.get("free_used", 0) >= FREE_LIMIT:
        await msg.answer("Бесплатный лимит закончился\n\nНажми Купить")
        return

    prompt = f"""
Задай вопрос по теме {user['subject']}.
Формат: A B C D
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )

    q = response.choices[0].message.content

    user["last_question"] = q

    if not is_premium(uid):
        user["free_used"] = user.get("free_used", 0) + 1

    save_users()

    await msg.answer(q, reply_markup=answers_kb)

# ====== ОТВЕТ ======
@dp.message_handler(lambda msg: msg.text in ["A","B","C","D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users[uid]

    prompt = f"""
Вопрос:
{user['last_question']}

Ответ:
{msg.text}

Скажи: правильно или нет + объяснение
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )

    res = response.choices[0].message.content

    await msg.answer(res)
    await send_question(msg)

# ====== ЗАПУСК ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
