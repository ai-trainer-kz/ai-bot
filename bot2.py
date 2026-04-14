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
ADMIN_ID = 8398266271
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

main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("🚀 Начать", "▶️ Тест")
main_kb.add("💰 Купить")

subjects_kb = ReplyKeyboardMarkup(resize_keyboard=True)
subjects_kb.add("Математика", "История")
subjects_kb.add("Биология", "Физика")
subjects_kb.add("Химия")

level_kb = ReplyKeyboardMarkup(resize_keyboard=True)
level_kb.add("Лёгкий", "Средний", "Сложный")

answers_kb = ReplyKeyboardMarkup(resize_keyboard=True)
answers_kb.add("A", "B", "C", "D")


def control_kb(lang):
    return ReplyKeyboardMarkup(resize_keyboard=True).add(
        t(lang, "⬅️ Назад", "⬅️ Артқа", "⬅️ Back"),
        t(lang, "🏁 Завершить", "🏁 Аяқтау", "🏁 Finish")
    )


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
    await msg.answer("Готово 👍", reply_markup=main_kb)


# ====== КУПИТЬ ======
@dp.message_handler(lambda msg: msg.text == "💰 Купить")
async def buy(msg: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 7 дней — 5000", callback_data="buy_7")],
        [InlineKeyboardButton(text="💎 30 дней — 10000", callback_data="buy_30")]
    ])

    await msg.answer("💎 Выбери тариф:", reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "buy_7")
async def buy7(callback: types.CallbackQuery):
    await callback.message.answer("💳 Kaspi: 4400430352720152\n\nНажми 'Оплатил'")
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data == "buy_30")
async def buy30(callback: types.CallbackQuery):
    await callback.message.answer("💳 Kaspi: 4400430352720152\n\nНажми 'Оплатил'")
    await callback.answer()


# ====== МЕНЮ ======
@dp.message_handler(lambda msg: msg.text in ["🚀 Начать", "▶️ Тест"])
async def menu(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid].get("lang", "ru")

    await msg.answer(
        t(lang, "Выбери предмет 👇", "Пәнді таңда 👇", "Choose subject 👇"),
        reply_markup=subjects_kb
    )


# ====== ПРЕДМЕТ ======
@dp.message_handler(lambda msg: msg.text in ["Математика", "История", "Биология", "Физика", "Химия"])
async def subject(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["subject"] = msg.text
    save_users()

    await msg.answer("Выбери уровень:", reply_markup=level_kb)


# ====== УРОВЕНЬ ======
@dp.message_handler(lambda msg: msg.text in ["Лёгкий", "Средний", "Сложный"])
async def level(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["difficulty"] = msg.text
    save_users()

    await send_question(msg)


# ====== ВОПРОС ======
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]

    lang = user.get("lang", "ru")

    if not is_premium(uid) and user.get("free_used", 0) >= FREE_LIMIT:
        await msg.answer(t(lang, "❌ Лимит закончился", "❌ Лимит бітті", "❌ Limit reached"))
        return

    if lang == "kz":
        prompt = "Тек қазақ тілінде 1 тест сұрағы (A,B,C,D) және дұрыс жауап"
    elif lang == "en":
        prompt = "ONLY in English: create 1 test question (A,B,C,D) with correct answer"
    else:
        prompt = "Сделай 1 тест вопрос (A,B,C,D) и укажи правильный ответ"

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


# ====== ОТВЕТ ======
@dp.message_handler(lambda msg: msg.text in ["A", "B", "C", "D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users.get(uid)

    lang = user.get("lang", "ru")

    if lang == "kz":
        prompt = f"Сен тек қазақ тілінде жауап бер!\n{user['last_question']}\nЖауап: {msg.text}"
    elif lang == "en":
        prompt = f"You MUST answer ONLY in English!\n{user['last_question']}\nAnswer: {msg.text}"
    else:
        prompt = f"{user['last_question']}\nОтвет: {msg.text}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    res = response.choices[0].message.content

    await msg.answer(res, reply_markup=control_kb(lang))
    await send_question(msg)


# ====== КНОПКИ ======
@dp.message_handler(lambda msg: msg.text in ["⬅️ Назад", "⬅️ Артқа", "⬅️ Back"])
async def back(msg: types.Message):
    await menu(msg)


@dp.message_handler(lambda msg: msg.text in ["🏁 Завершить", "🏁 Аяқтау", "🏁 Finish"])
async def finish(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["last_question"] = None
    save_users()

    await msg.answer("✅ Тест завершён", reply_markup=main_kb)


# ====== RUN ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
