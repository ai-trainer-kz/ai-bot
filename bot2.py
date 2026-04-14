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


# ===== БАЗА =====
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


# ===== ПЕРЕВОД =====
def t(lang, ru, kz, en):
    return {"ru": ru, "kz": kz, "en": en}.get(lang, ru)


# ===== КНОПКИ =====
def lang_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Русский 🇷🇺", "Қазақ 🇰🇿", "English 🇺🇸")
    return kb


def subject_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        t(lang, "📐 Математика", "📐 Математика", "📐 Math"),
        t(lang, "📖 История", "📖 Тарих", "📖 History"),
        t(lang, "🧪 Наука", "🧪 Ғылым", "🧪 Science")
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
        t(lang, "🏠 Домой", "🏠 Басты", "🏠 Home")
    )
    kb.add("A", "B", "C", "D")
    return kb


def pay_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        t(lang, "💳 Оплатил", "💳 Төледім", "💳 I paid"),
        t(lang, "🏠 Домой", "🏠 Басты", "🏠 Home")
    )
    return kb


def admin_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="7 дней", callback_data=f"give7_{uid}"),
            InlineKeyboardButton(text="30 дней", callback_data=f"give30_{uid}")
        ]
    ])


# ===== СТАРТ =====
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid] = {
        "step": "lang",
        "lang": "ru",
        "subject": None,
        "level": None,
        "q": 0,
        "score": 0,
        "premium": False,
        "total": 0
    }

    save_users()

    await msg.answer("Выбери язык 🌍", reply_markup=lang_kb())


# ===== ЯЗЫК =====
@dp.message_handler(lambda m: m.text in ["Русский 🇷🇺", "Қазақ 🇰🇿", "English 🇺🇸"])
async def set_lang(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid]["lang"] = {
        "Русский 🇷🇺": "ru",
        "Қазақ 🇰🇿": "kz",
        "English 🇺🇸": "en"
    }[msg.text]

    users[uid]["step"] = "subject"
    save_users()

    await msg.answer("Выбери предмет 📚", reply_markup=subject_kb(users[uid]["lang"]))


# ===== ПРЕДМЕТ =====
@dp.message_handler(lambda m: m.text.startswith("📐") or m.text.startswith("📖") or m.text.startswith("🧪"))
async def set_subject(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid]["subject"] = msg.text
    users[uid]["step"] = "level"
    save_users()

    await msg.answer("Выбери уровень 🎯", reply_markup=level_kb(users[uid]["lang"]))


# ===== УРОВЕНЬ =====
@dp.message_handler(lambda m: "🟢" in m.text or "🟡" in m.text or "🔴" in m.text)
async def set_level(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid]["level"] = msg.text
    users[uid]["step"] = "test"
    users[uid]["q"] = 0
    users[uid]["score"] = 0

    await send_q(msg)


# ===== ВОПРОС =====
async def send_q(msg):
    uid = str(msg.from_user.id)
    u = users[uid]

    if u["q"] >= 5:
        await finish(msg)
        return

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"1 question A-D, {u['subject']}, {u['level']}, language {u['lang']}"
        }]
    )

    q = res.choices[0].message.content
    u["last"] = q
    save_users()

    await msg.answer(q, reply_markup=control_kb(u["lang"]))


# ===== ОТВЕТ =====
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    u = users[uid]

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"{u['last']} answer {msg.text}"}]
    )

    txt = res.choices[0].message.content

    if "correct" in txt.lower() or "дұрыс" in txt.lower():
        u["score"] += 1

    u["q"] += 1
    save_users()

    await msg.answer(txt)
    await send_q(msg)


# ===== ФИНИШ =====
async def finish(msg):
    uid = str(msg.from_user.id)
    u = users[uid]

    u["total"] += 1
    save_users()

    await msg.answer(f"🏁 Результат: {u['score']}/5")

    if not u["premium"]:
        await ask_pay(msg)


# ===== ОПЛАТА =====
async def ask_pay(msg):
    uid = str(msg.from_user.id)

    await msg.answer(
        f"💳 Kaspi: {KASPI_NUMBER}\n\nНажми 'Оплатил'\n{SUPPORT}",
        reply_markup=pay_kb(users[uid]["lang"])
    )


@dp.message_handler(lambda m: "Оплатил" in m.text or "Төледім" in m.text or "paid" in m.text.lower())
async def paid(msg: types.Message):
    await bot.send_message(
        ADMIN_ID,
        f"Оплата от {msg.from_user.id}",
        reply_markup=admin_kb(msg.from_user.id)
    )


@dp.callback_query_handler(lambda c: "give" in c.data)
async def give(call):
    uid = call.data.split("_")[1]

    users[uid]["premium"] = True
    save_users()

    await bot.send_message(uid, "Доступ выдан!")


# ===== НАЗАД =====
@dp.message_handler(lambda m: "Назад" in m.text or "Артқа" in m.text or "Back" in m.text)
async def back(msg: types.Message):
    uid = str(msg.from_user.id)
    step = users[uid]["step"]

    if step == "level":
        users[uid]["step"] = "subject"
        await msg.answer("Назад к предметам", reply_markup=subject_kb(users[uid]["lang"]))

    elif step == "test":
        users[uid]["step"] = "level"
        await msg.answer("Назад к уровням", reply_markup=level_kb(users[uid]["lang"]))


# ===== ДОМОЙ =====
@dp.message_handler(lambda m: "Домой" in m.text or "Басты" in m.text or "Home" in m.text)
async def home(msg: types.Message):
    await start(msg)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
