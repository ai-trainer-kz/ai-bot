import os
import logging
import json
from datetime import datetime

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
FREE_LIMIT = 10


# ====== UTILS ======
def t(lang, ru, kz, en):
    if lang == "kz":
        return kz
    elif lang == "en":
        return en
    return ru


# ====== DATA ======
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


def is_premium(uid):
    user = users.get(uid)
    if not user or not user.get("premium"):
        return False

    expires = user.get("expires")
    if not expires:
        return False

    expires_date = datetime.strptime(expires, "%Y-%m-%d")
    return datetime.now() <= expires_date


# ====== КНОПКИ ======
lang_kb = ReplyKeyboardMarkup(resize_keyboard=True)
lang_kb.add("Русский 🇷🇺", "Қазақ 🇰🇿", "English 🇺🇸")

answers_kb = ReplyKeyboardMarkup(resize_keyboard=True)
answers_kb.add("A", "B", "C", "D")


def main_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        t(lang, "🚀 Начать", "🚀 Бастау", "🚀 Start"),
        t(lang, "▶️ Тест", "▶️ Тест", "▶️ Test")
    )
    kb.add(
        t(lang, "🌍 Язык", "🌍 Тіл", "🌍 Language")
    )
    return kb


def subjects_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "История")
    kb.add("Биология", "Физика")
    kb.add("Химия")
    return kb


def level_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        t(lang, "Лёгкий", "Жеңіл", "Easy"),
        t(lang, "Средний", "Орташа", "Medium"),
        t(lang, "Сложный", "Қиын", "Hard")
    )
    return kb


def control_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        t(lang, "⬅️ Назад", "⬅️ Артқа", "⬅️ Back"),
        t(lang, "🏁 Завершить", "🏁 Аяқтау", "🏁 Finish")
    )
    kb.add(
        t(lang, "🏠 Меню", "🏠 Мәзір", "🏠 Menu")
    )
    return kb


# ====== START ======
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid] = users.get(uid, {
        "lang": "ru",
        "free_used": 0,
        "premium": False,
        "expires": None
    })

    save_users()
    await msg.answer("Выбери язык 🌍", reply_markup=lang_kb)


# ====== ЯЗЫК ======
@dp.message_handler(lambda msg: msg.text in ["Русский 🇷🇺", "Қазақ 🇰🇿", "English 🇺🇸"])
async def set_lang(msg: types.Message):
    uid = str(msg.from_user.id)

    if "Русский" in msg.text:
        users[uid]["lang"] = "ru"
    elif "Қазақ" in msg.text:
        users[uid]["lang"] = "kz"
    else:
        users[uid]["lang"] = "en"

    save_users()

    lang = users[uid]["lang"]

    await msg.answer(
        t(lang, "Готово 👍", "Дайын 👍", "Done 👍"),
        reply_markup=main_kb(lang)
    )


# ====== МЕНЮ ======
@dp.message_handler(lambda msg: msg.text in ["🚀 Начать", "▶️ Тест", "🚀 Бастау", "▶️ Test"])
async def menu(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid].get("lang", "ru")

    await msg.answer(
        t(lang, "Выбери предмет 👇", "Пәнді таңда 👇", "Choose subject 👇"),
        reply_markup=subjects_kb(lang)
    )


# ====== SUBJECT ======
@dp.message_handler(lambda msg: msg.text in ["Математика", "История", "Биология", "Физика", "Химия"])
async def subject(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid].get("lang", "ru")

    users[uid]["subject"] = msg.text
    save_users()

    await msg.answer(
        t(lang, "Выбери уровень:", "Деңгейді таңда:", "Choose level:"),
        reply_markup=level_kb(lang)
    )


# ====== LEVEL ======
@dp.message_handler(lambda msg: msg.text in ["Лёгкий", "Средний", "Сложный", "Жеңіл", "Орташа", "Қиын", "Easy", "Medium", "Hard"])
async def level(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["difficulty"] = msg.text
    save_users()

    await send_question(msg)


# ====== QUESTION ======
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user.get("lang", "ru")

    if not is_premium(uid) and user.get("free_used", 0) >= FREE_LIMIT:
        await msg.answer(t(lang, "❌ Лимит закончился", "❌ Лимит бітті", "❌ Limit reached"))
        return

    if lang == "kz":
        prompt = f"""
Тек қазақ тілінде жауап бер.
Сұрақ құрастыр (A,B,C,D).
ДҰРЫС ЖАУАПТЫ КӨРСЕТПЕ!
"""
    elif lang == "en":
        prompt = f"""
ONLY in English.
Create 1 question (A,B,C,D).
DO NOT show correct answer.
"""
    else:
        prompt = f"""
Сделай вопрос (A,B,C,D).
НЕ показывай правильный ответ.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    q = response.choices[0].message.content
    user["last_question"] = q

    if not is_premium(uid):
        user["free_used"] += 1

    save_users()

    await msg.answer(q, reply_markup=answers_kb)


# ====== ANSWER ======
@dp.message_handler(lambda msg: msg.text in ["A", "B", "C", "D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users.get(uid)
    lang = user.get("lang", "ru")

    if lang == "kz":
        prompt = f"""
Тек қазақ тілінде жауап бер!

Сұрақ:
{user['last_question']}

Жауап: {msg.text}

Дұрыс па, түсіндір.
"""
    elif lang == "en":
        prompt = f"""
Answer ONLY in English!

Question:
{user['last_question']}

Answer: {msg.text}

Explain if correct or not.
"""
    else:
        prompt = f"""
Вопрос:
{user['last_question']}

Ответ: {msg.text}

Правильно или нет и объясни.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    res = response.choices[0].message.content

    await msg.answer(res, reply_markup=control_kb(lang))


# ====== NAVIGATION ======
@dp.message_handler(lambda msg: msg.text in ["⬅️ Назад", "⬅️ Артқа", "⬅️ Back"])
async def back(msg: types.Message):
    await menu(msg)


@dp.message_handler(lambda msg: msg.text in ["🏁 Завершить", "🏁 Аяқтау", "🏁 Finish"])
async def finish(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["last_question"] = None
    save_users()

    lang = users[uid].get("lang", "ru")

    await msg.answer(
        t(lang, "✅ Тест завершён", "✅ Тест аяқталды", "✅ Test finished"),
        reply_markup=main_kb(lang)
    )


@dp.message_handler(lambda msg: msg.text in ["🏠 Меню", "🏠 Мәзір", "🏠 Menu"])
async def to_menu(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid].get("lang", "ru")

    await msg.answer(
        t(lang, "Главное меню", "Басты мәзір", "Main menu"),
        reply_markup=main_kb(lang)
    )


# ====== RUN ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
