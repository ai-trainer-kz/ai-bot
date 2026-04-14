import os
import logging
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
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

# ====== НАСТРОЙКИ ======
FREE_LIMIT = 10

# ====== ПРОВЕРКА ПРЕМИУМА ======
def is_premium(user_id):
    user = users.get(user_id)

    if not user:
        return False

    if not user.get("premium"):
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

# ====== ВЫДАЧА ПРЕМИУМА (вручную) ======
def give_premium(user_id):
    expires = datetime.now() + timedelta(days=30)

    users[user_id]["premium"] = True
    users[user_id]["expires"] = expires.strftime("%Y-%m-%d")

    save_users()

# ====== ТЕКСТЫ ======
TEXTS = {
    "ru": {
        "start": "Привет! Я AI-тренер 💪",
        "choose_lang": "Выбери язык 🌍",
        "limit": "❌ Бесплатный лимит закончился.",
    }
}

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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

pay_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
])

# ====== АДМИН ФУНКЦИИ ======

@dp.message_handler(commands=["give"])
async def give_access(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return

    try:
        args = msg.get_args().split()
        user_id = args[0]
        days = int(args[1]) if len(args) > 1 else 3
    except:
        await msg.answer("Формат: /give user_id 3")
        return

    expires = datetime.now() + timedelta(days=days)

    if user_id not in users:
        users[user_id] = {
            "xp": 0,
            "level": 1,
            "streak": 0,
            "lives": 3,
            "lang": "ru",
            "free_used": 0
        }

    users[user_id]["premium"] = True
    users[user_id]["expires"] = expires.strftime("%Y-%m-%d")

    save_users()

    await msg.answer(f"✅ Дал доступ {user_id} на {days} дней")


@dp.message_handler(commands=["remove"])
async def remove_access(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return

    user_id = msg.get_args()

    if user_id in users:
        users[user_id]["premium"] = False
        users[user_id]["expires"] = None
        save_users()

    await msg.answer(f"❌ Доступ убран у {user_id}")


@dp.message_handler(commands=["user"])
async def get_user(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return

    user_id = msg.get_args()

    user = users.get(user_id)

    if not user:
        await msg.answer("Нет такого пользователя")
        return

    text = f"""
ID: {user_id}
Premium: {user.get('premium')}
Expires: {user.get('expires')}
XP: {user.get('xp')}
"""

    await msg.answer(text)


@dp.message_handler(commands=["users"])
async def show_users(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return

    text = "👥 Пользователи:\n\n"

    for uid, u in users.items():
        text += f"{uid} | premium: {u.get('premium')} | xp: {u.get('xp')}\n"

    await msg.answer(text[:4000])

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

    await msg.answer(TEXTS["ru"]["start"], reply_markup=main_kb)

# ====== КУПИТЬ ======
@dp.message_handler(lambda msg: msg.text == "💰 Купить")
async def buy(msg: types.Message):
    text = """
🔥 ПОЛНЫЙ ДОСТУП — 10 000 тг / месяц

Что ты получаешь:
text = """
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

# ====== НАЗАД ======
@dp.message_handler(lambda msg: msg.text == "🔙 Назад")
async def back(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid].pop("subject", None)
    users[uid].pop("difficulty", None)
    save_users()
    await msg.answer("Выбери предмет 👇", reply_markup=subjects_kb)

# ====== СТОП ======
@dp.message_handler(lambda msg: msg.text == "🛑 Завершить")
async def stop(msg: types.Message):
    await msg.answer("Тест завершён 👍", reply_markup=main_kb)

# ====== ВОПРОС ======
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]

    # 🔥 ЛИМИТ + ПРЕМИУМ
    if not is_premium(uid) and user.get("free_used", 0) >= FREE_LIMIT:
        await msg.answer(TEXTS["ru"]["limit"] + "\n\nНажми 💰 Купить")
        return

    prompt = f"""
Задай вопрос по теме {user['subject']}.
Язык: {user.get('lang')}
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

Скажи:
правильно или нет + объяснение
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )

    res = response.choices[0].message.content

    if "прав" in res.lower():
        user["xp"] += 10
        user["streak"] += 1
    else:
        user["lives"] -= 1
        user["streak"] = 0

    if user["lives"] <= 0:
        await msg.answer("💀 Жизни закончились", reply_markup=main_kb)
        user["lives"] = 3
        save_users()
        return

    save_users()

    await msg.answer(res)
    await msg.answer(f"🔥 {user['streak']} | ❤️ {user['lives']} | ⭐ {user['xp']}")

    await send_question(msg)

# ====== ЗАПУСК ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
