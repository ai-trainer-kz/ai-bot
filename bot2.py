import os
import json
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ADMIN_ID = 8398266271

KASPI_NUMBER = "4400430352720152"
SUPPORT = "@ai_teacher1_support"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

DATA_FILE = "users.json"


# ================== БАЗА ==================
def load_users():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_users():
    with open(DATA_FILE, "w") as f:
        json.dump(users, f)


users = load_users()


# ================== ПЕРЕВОД ==================
def t(lang, ru, kz, en):
    return {"ru": ru, "kz": kz, "en": en}.get(lang, ru)


# ================== КНОПКИ ==================
def main_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        t(lang, "🚀 Старт", "🚀 Бастау", "🚀 Start"),
        t(lang, "📚 Тест", "📚 Тест", "📚 Test"),
        t(lang, "📊 Статистика", "📊 Статистика", "📊 Stats")
    )
    return kb


def level_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        t(lang, "🟢 Лёгкий", "🟢 Жеңіл", "🟢 Easy"),
        t(lang, "🟡 Средний", "🟡 Орташа", "🟡 Medium"),
        t(lang, "🔴 Сложный", "🔴 Қиын", "🔴 Hard")
    )
    return kb


def control_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        t(lang, "⬅️ Назад", "⬅️ Артқа", "⬅️ Back"),
        t(lang, "🏁 Завершить", "🏁 Аяқтау", "🏁 Finish"),
        t(lang, "🏠 Меню", "🏠 Мәзір", "🏠 Menu")
    )
    kb.add("A", "B", "C", "D")
    return kb


def pay_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        t(lang, "💳 Оплатил", "💳 Төледім", "💳 I paid"),
        t(lang, "🏠 Меню", "🏠 Мәзір", "🏠 Menu")
    )
    return kb


def admin_pay_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ 7 дней", callback_data=f"give7_{user_id}"),
            InlineKeyboardButton(text="🚀 30 дней", callback_data=f"give30_{user_id}")
        ]
    ])


# ================== СТАРТ ==================
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    uid = str(msg.from_user.id)

    if uid not in users:
        users[uid] = {
            "lang": "ru",
            "premium": False,
            "expires": None,
            "q_count": 0,
            "score": 0,
            "total_tests": 0,
            "total_correct": 0,
            "streak": 0
        }
        save_users()

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Русский 🇷🇺", "Қазақ 🇰🇿", "English 🇺🇸")

    await msg.answer("Выбери язык 🌍", reply_markup=kb)


# ================== ЯЗЫК ==================
@dp.message_handler(lambda msg: msg.text in ["Русский 🇷🇺", "Қазақ 🇰🇿", "English 🇺🇸"])
async def set_lang(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid]["lang"] = {
        "Русский 🇷🇺": "ru",
        "Қазақ 🇰🇿": "kz",
        "English 🇺🇸": "en"
    }[msg.text]

    save_users()

    lang = users[uid]["lang"]

    await msg.answer("Готово 👍", reply_markup=main_kb(lang))


# ================== СТАРТ (уровни) ==================
@dp.message_handler(lambda msg: msg.text in ["🚀 Старт", "🚀 Бастау", "🚀 Start"])
async def choose_level(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    await msg.answer(
        t(lang, "Выбери уровень 👇", "Деңгейді таңда 👇", "Choose level 👇"),
        reply_markup=level_kb(lang)
    )


# ================== ВЫБОР УРОВНЯ ==================
@dp.message_handler(lambda msg: msg.text in [
    "🟢 Лёгкий", "🟡 Средний", "🔴 Сложный",
    "🟢 Жеңіл", "🟡 Орташа", "🔴 Қиын",
    "🟢 Easy", "🟡 Medium", "🔴 Hard"
])
async def set_level(msg: types.Message):
    uid = str(msg.from_user.id)

    level_map = {
        "🟢 Лёгкий": "easy", "🟢 Жеңіл": "easy", "🟢 Easy": "easy",
        "🟡 Средний": "medium", "🟡 Орташа": "medium", "🟡 Medium": "medium",
        "🔴 Сложный": "hard", "🔴 Қиын": "hard", "🔴 Hard": "hard"
    }

    users[uid]["level"] = level_map[msg.text]
    users[uid]["q_count"] = 0
    users[uid]["score"] = 0

    await send_question(msg)


# ================== ВОПРОС ==================
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    if user["q_count"] >= 10:
        await finish_test(msg)
        return

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"Generate question (A-D), level {user.get('level','medium')} in {lang}. No answer."
        }]
    )

    q = response.choices[0].message.content
    user["last_question"] = q

    save_users()

    await msg.answer(q, reply_markup=control_kb(lang))


# ================== ОТВЕТ ==================
@dp.message_handler(lambda msg: msg.text in ["A", "B", "C", "D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users[uid]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"{user['last_question']}\nUser answer: {msg.text}\nCheck correct"
        }]
    )

    result = response.choices[0].message.content

    if "correct" in result.lower() or "дұрыс" in result.lower():
        user["score"] += 1
        user["total_correct"] += 1
        user["streak"] += 1
    else:
        user["streak"] = 0

    user["q_count"] += 1
    save_users()

    await msg.answer(result)

    await send_question(msg)


# ================== ФИНИШ ==================
async def finish_test(msg):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    user["total_tests"] += 1
    save_users()

    await msg.answer(
        f"🏁 Результат: {user['score']}/10",
        reply_markup=main_kb(lang)
    )

    # 👉 сразу предлагаем оплату
    if not user.get("premium"):
        await ask_payment(msg)


# ================== ОПЛАТА ==================
async def ask_payment(msg):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    await msg.answer(
        f"🔒 Доступ закончился!\n\n💳 Kaspi: {KASPI_NUMBER}\n\nПосле оплаты нажми 'Оплатил'\n\n{SUPPORT}",
        reply_markup=pay_kb(lang)
    )


@dp.message_handler(lambda msg: msg.text in ["💳 Оплатил", "💳 Төледім", "💳 I paid"])
async def paid(msg: types.Message):
    user = msg.from_user

    await bot.send_message(
        ADMIN_ID,
        f"💰 Новый платеж!\n@{user.username}\nID: {user.id}",
        reply_markup=admin_pay_kb(user.id)
    )

    await msg.answer("⏳ Ожидай подтверждения")


@dp.callback_query_handler(lambda c: c.data.startswith("give"))
async def give(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    uid = callback.data.split("_")[1]
    days = 7 if "give7" in callback.data else 30

    users[uid]["premium"] = True
    users[uid]["expires"] = (datetime.now() + timedelta(days=days)).isoformat()

    save_users()

    await bot.send_message(uid, f"🔥 Доступ на {days} дней активирован!")
    await callback.answer("Выдано")


# ================== МЕНЮ ==================
@dp.message_handler(lambda msg: msg.text.lower() in [
    "⬅️ назад", "⬅️ артқа", "⬅️ back",
    "🏠 меню", "🏠 мәзір", "🏠 menu"
])
async def back(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    await msg.answer("🏠", reply_markup=main_kb(lang))


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
