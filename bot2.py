import os
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8398266271

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ===== "БАЗА" =====
users = {}

FREE_LIMIT = 10

# ===== КНОПКИ =====
def lang_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")
    return kb

def subject_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "История")
    kb.add("Биология", "Назад")
    return kb

def level_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Легкий", "Средний", "Сложный")
    kb.add("Назад")
    return kb

def start_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Начать тест")
    kb.add("Назад")
    return kb

def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    kb.add("Назад")
    return kb

def pay_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 Оплатил", "Назад")
    return kb

# ===== СТАРТ =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    users[message.from_user.id] = {
        "step": "lang",
        "q": 0,
        "score": 0,
        "free_used": 0,
        "premium_until": None
    }
    await message.answer("Выберите язык", reply_markup=lang_kb())

# ===== ЯЗЫК =====
@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def lang(message: types.Message):
    users[message.from_user.id]["step"] = "subject"
    await message.answer("Выберите предмет", reply_markup=subject_kb())

# ===== ПРЕДМЕТ =====
@dp.message_handler(lambda m: m.text in ["Математика", "История", "Биология"])
async def subject(message: types.Message):
    users[message.from_user.id]["step"] = "level"
    await message.answer("Выберите уровень", reply_markup=level_kb())

# ===== УРОВЕНЬ =====
@dp.message_handler(lambda m: m.text in ["Легкий", "Средний", "Сложный"])
async def level(message: types.Message):
    users[message.from_user.id]["step"] = "ready"
    await message.answer("Готов начать?", reply_markup=start_kb())

# ===== ПРОВЕРКА ДОСТУПА =====
def has_access(user):
    if user["premium_until"]:
        if datetime.now() < user["premium_until"]:
            return True
    return False

# ===== СТАРТ ТЕСТА =====
@dp.message_handler(lambda m: m.text == "Начать тест")
async def start_test(message: types.Message):
    user = users[message.from_user.id]

    if not has_access(user) and user["free_used"] >= FREE_LIMIT:
        await message.answer(
            "❌ Бесплатный лимит закончился\n\n"
            "Kaspi: 87001234567\n"
            "7 дней — 1000 тг\n30 дней — 3000 тг\n\n"
            "После оплаты нажми 'Оплатил'",
            reply_markup=pay_kb()
        )
        return

    user["q"] = 1
    user["score"] = 0
    user["step"] = "test"

    await send_question(message)

# ===== ВОПРОС =====
async def send_question(message):
    user = users[message.from_user.id]
    q = user["q"]

    text = f"Вопрос {q}\nСколько будет 2+2?\n\nA)3\nB)4\nC)5\nD)6"
    await message.answer(text, reply_markup=answer_kb())

# ===== ОТВЕТ =====
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def answer(message: types.Message):
    user = users[message.from_user.id]

    if message.text == "B":
        user["score"] += 1

    user["q"] += 1
    user["free_used"] += 1

    if user["q"] > 5:
        await message.answer(f"Результат: {user['score']}/5")
        user["step"] = "ready"
        return

    await send_question(message)

# ===== ОПЛАТИЛ =====
@dp.message_handler(lambda m: m.text == "💰 Оплатил")
async def paid(message: types.Message):
    user_id = message.from_user.id

    await bot.send_message(
        ADMIN_ID,
        f"Пользователь оплатил:\nID: {user_id}\n@{message.from_user.username}"
    )

    await message.answer("⏳ Проверяем оплату...")

# ===== АДМИН ВЫДАЁТ ДОСТУП =====
@dp.message_handler(commands=['give7'])
async def give7(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    user_id = int(message.get_args())
    users[user_id]["premium_until"] = datetime.now() + timedelta(days=7)

    await message.answer("Выдано 7 дней")

@dp.message_handler(commands=['give30'])
async def give30(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    user_id = int(message.get_args())
    users[user_id]["premium_until"] = datetime.now() + timedelta(days=30)

    await message.answer("Выдано 30 дней")

# ===== НАЗАД =====
@dp.message_handler(lambda m: m.text == "Назад")
async def back(message: types.Message):
    user = users.get(message.from_user.id)

    if not user:
        await start(message)
        return

    step = user["step"]

    if step == "subject":
        user["step"] = "lang"
        await message.answer("Выберите язык", reply_markup=lang_kb())

    elif step == "level":
        user["step"] = "subject"
        await message.answer("Выберите предмет", reply_markup=subject_kb())

    elif step == "ready":
        user["step"] = "level"
        await message.answer("Выберите уровень", reply_markup=level_kb())

    elif step == "test":
        user["step"] = "ready"
        await message.answer("Готов начать?", reply_markup=start_kb())

# ===== ЗАПУСК =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
