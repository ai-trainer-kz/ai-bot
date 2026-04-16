import os
import logging
import json
from datetime import datetime, timedelta
import re

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 8398266271

FREE_MESSAGES = 10
KASPI = "4400430352720152"

MODEL = "gpt-4o-mini"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

users = {}

# ===== SAVE / LOAD =====
def save_users():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_users():
    global users
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            users = json.load(f)
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
    kb.add("7 дней - 5000 тг")
    kb.add("30 дней - 10000 тг")
    kb.add("⬅️ Назад")
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📋 Пользователи")
    kb.add("🎁 Выдать 7 дней")
    kb.add("🎁 Выдать 30 дней")
    kb.add("⬅️ Назад")
    return kb

# ===== USER =====
def ensure_user(uid):
    if uid not in users:
        users[uid] = {
            "subject": None,
            "level": "Средний",
            "lang": "ru",
            "history": [],
            "correct": None,
            "total": 0,
            "correct_answers": 0,
            "premium_until": None
        }

# ===== GPT =====
def ask_gpt(u, mode="question", user_text=None):

    if mode == "question":
        system = "Сгенерируй ОДИН тест:\nВопрос\nA\nB\nC\nD\nПравильный ответ: X"
    else:
        system = "Объясни решение кратко"

    messages = [{"role": "system", "content": system}]

    if user_text:
        messages.append({"role": "user", "content": user_text})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )

    text = resp.choices[0].message.content
    return text

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    uid = str(message.from_user.id)
    ensure_user(uid)

    await message.answer("🤖 AI ЕНТ Тренер", reply_markup=main_kb(message.from_user.id))

# ===== ЯЗЫК =====
@dp.message_handler(lambda m: m.text == "🌐 Язык")
async def lang(message: types.Message):
    await message.answer("Выбери язык", reply_markup=lang_kb())

@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский","🇰🇿 Қазақша"])
async def set_lang(message: types.Message):
    uid = str(message.from_user.id)
    users[uid]["lang"] = "kz" if "🇰🇿" in message.text else "ru"
    await message.answer("Сохранено", reply_markup=main_kb(message.from_user.id))

# ===== ОБУЧЕНИЕ =====
@dp.message_handler(lambda m: m.text == "📚 Начать обучение")
async def learn(message: types.Message):
    await message.answer("Выбери предмет", reply_markup=subject_kb())

@dp.message_handler(lambda m: any(x in m.text for x in ["Математика","История","Биология","Химия"]))
async def subject(message: types.Message):
    uid = str(message.from_user.id)
    users[uid]["subject"] = message.text
    await message.answer("Выбери уровень", reply_markup=level_kb())

@dp.message_handler(lambda m: any(x in m.text for x in ["База","Средний","Сложный"]))
async def level(message: types.Message):
    uid = str(message.from_user.id)
    u = users[uid]

    u["total"] = 0
    u["correct_answers"] = 0

    text = ask_gpt(u)

    m = re.search(r"([ABCD])", text)
    if m:
        u["correct"] = m.group(1)

    text = re.sub(r"Правильный ответ.*", "", text)

    await message.answer(f"Вопрос 1/10\n{text}", reply_markup=answer_kb())

# ===== ОТВЕТ =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    uid = str(message.from_user.id)
    u = users[uid]

    u["total"] += 1

    if message.text == u["correct"]:
        u["correct_answers"] += 1
        res = "✅ Правильно"
    else:
        res = f"❌ Неправильно. Ответ: {u['correct']}"

    explain = ask_gpt(u, "explain", "Объясни")

    await message.answer(res + "\n\n" + explain)

    # ===== ФИНАЛ =====
    if u["total"] >= 10:
        percent = int(u["correct_answers"]*10)

        await message.answer(
            f"📊 Результат:\n\n{u['correct_answers']}/10\n{percent}%\n\n💰 Купить доступ",
            reply_markup=main_kb(message.from_user.id)
        )
        return

    text = ask_gpt(u)

    m = re.search(r"([ABCD])", text)
    if m:
        u["correct"] = m.group(1)

    text = re.sub(r"Правильный ответ.*", "", text)

    await message.answer(f"Вопрос {u['total']+1}/10\n{text}", reply_markup=answer_kb())

# ===== ОПЛАТА =====
@dp.message_handler(lambda m: m.text == "💰 Купить доступ")
async def pay(message: types.Message):
    await message.answer(f"Kaspi: {KASPI}", reply_markup=pay_kb())

# ===== АДМИН =====
@dp.message_handler(lambda m: m.text == "👑 Админ")
async def admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Админ панель", reply_markup=admin_kb())

@dp.message_handler(lambda m: m.text == "📋 Пользователи")
async def users_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(f"Всего: {len(users)}")

# ===== RUN =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
