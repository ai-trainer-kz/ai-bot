import os
import json
import re
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

USERS_FILE = "users.json"

# ===== LOAD =====
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
else:
    users = {}

def save_users():
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def ensure_user(user_id):
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {
            "lang": "ru",
            "step": "menu",
            "correct_count": 0,
            "wrong_count": 0,
            "welcome_done": False
        }
    return users[user_id]

# ===== KEYBOARDS =====
def main_kb(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Начать обучение")
    kb.add("💰 Купить доступ", "📊 Статус")
    kb.add("🌐 Язык")
    kb.add("⬅️ Назад")
    return kb

def lang_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")
    return kb

def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    kb.add("⬅️ Назад")
    return kb

# ===== START =====
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    u = ensure_user(message.from_user.id)

    if not u["welcome_done"]:
        if u["lang"] == "kz":
            await message.answer("🔥 AI ЕНТ Тренер\nБастау үшін таңда 👇")
        else:
            await message.answer("🔥 AI ЕНТ Тренер\nНачни обучение 👇")

        u["welcome_done"] = True
        save_users()

    await message.answer("Главное меню", reply_markup=main_kb(message.from_user.id))

# ===== LANGUAGE =====
@dp.message_handler(lambda m: "Язык" in (m.text or "") or "Тіл" in (m.text or ""))
async def choose_lang(message: types.Message):
    await message.answer("Выбери язык", reply_markup=lang_kb())

@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def set_lang(message: types.Message):
    u = users[str(message.from_user.id)]

    if "Қазақ" in message.text:
        u["lang"] = "kz"
        await message.answer("✅ Тіл өзгертілді")
    else:
        u["lang"] = "ru"
        await message.answer("✅ Язык изменён")

    save_users()
    await message.answer("Главное меню", reply_markup=main_kb(message.from_user.id))

# ===== BACK =====
@dp.message_handler(lambda m: "Назад" in (m.text or "") or "Артқа" in (m.text or ""))
async def back(message: types.Message):
    u = users[str(message.from_user.id)]
    u["step"] = "menu"
    save_users()

    await message.answer("Главное меню", reply_markup=main_kb(message.from_user.id))

# ===== START LEARNING =====
@dp.message_handler(lambda m: "Начать обучение" in (m.text or ""))
async def start_learning(message: types.Message):
    u = users[str(message.from_user.id)]

    u["step"] = "test"
    u["correct"] = "B"  # пример
    save_users()

    await message.answer(
        "Вопрос: 2+2*2 = ?\nA)4\nB)6\nC)8\nD)10",
        reply_markup=answer_kb()
    )

# ===== ANSWERS =====
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def answer(message: types.Message):
    u = users[str(message.from_user.id)]

    if u.get("step") != "test":
        return

    user_answer = message.text

    if user_answer == u.get("correct"):
        u["correct_count"] += 1

        if u["lang"] == "kz":
            await message.answer("✅ Дұрыс!")
        else:
            await message.answer("✅ Правильно!")

    else:
        u["wrong_count"] += 1

        if u["lang"] == "kz":
            await message.answer(f"❌ Қате! Дұрыс жауап: {u.get('correct')}")
        else:
            await message.answer(f"❌ Неправильно! Правильный ответ: {u.get('correct')}")

    save_users()

# ===== STATUS =====
@dp.message_handler(lambda m: "Статус" in (m.text or ""))
async def status(message: types.Message):
    u = users[str(message.from_user.id)]

    await message.answer(
        f"""📊 Статистика

✅ {u.get("correct_count",0)}
❌ {u.get("wrong_count",0)}"""
    )

# ===== BUY =====
@dp.message_handler(lambda m: "Купить доступ" in (m.text or ""))
async def buy(message: types.Message):
    await message.answer("💰 Оплата через Kaspi")

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
