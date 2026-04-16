import os
import logging
import json
from datetime import datetime, timedelta
import re

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
        if u.get("premium_until"):
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
                if users[uid].get("premium_until"):
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

def pay_admin_kb(user_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⚡ 7 дней", callback_data=f"give7_{user_id}"),
        InlineKeyboardButton("🚀 30 дней", callback_data=f"give30_{user_id}")
    )
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
            "correct": None,
            "correct_count": 0,
            "wrong_count": 0,
            "welcome_done": False
        }
        save_users()

# ===== GPT =====
def ask_gpt(u, user_text=None, mode="question"):

    if mode == "question":
        system = f"""
Ты преподаватель ЕНТ.
ПРЕДМЕТ: {u["subject"]}

Сделай 1 вопрос с вариантами A B C D
В конце напиши: Правильный ответ: X
"""
    else:
        system = "Объясни решение кратко"

    messages = [{"role": "system", "content": system}]
    messages += u["history"][-5:]

    if user_text:
        messages.append({"role": "user", "content": user_text})
    else:
        messages.append({"role": "user", "content": "Начни тест"})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )

    answer = resp.choices[0].message.content

    for s in ["\\(", "\\)", "\\[", "\\]", "**"]:
        answer = answer.replace(s, "")

    u["history"].append({"role": "assistant", "content": answer})
    save_users()
    return answer

# ===== СТАРТ =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[message.from_user.id]

    if not u["welcome_done"]:
        await message.answer("""🔥 AI ЕНТ Тренер

🤖 Тесты + объяснение
📊 Статистика

Начни 👇""")

        u["welcome_done"] = True
        save_users()

    await message.answer("Главное меню", reply_markup=main_kb(message.from_user.id))

# ===== СТАТУС =====
@dp.message_handler(lambda m: "Статус" in (m.text or ""))
async def status(message: types.Message):
    u = users[message.from_user.id]

    text = f"""📊 Статистика

✅ {u.get("correct_count",0)}
❌ {u.get("wrong_count",0)}"""

    await message.answer(text)

# ===== ОБУЧЕНИЕ =====
@dp.message_handler(lambda m: m.text == "📚 Начать обучение")
async def choose_subject(message: types.Message):
    users[message.from_user.id]["step"] = "subject"
    await message.answer("Выбери предмет", reply_markup=subject_kb())

@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["Математика","История","Биология","Химия"]))
async def choose_level(message: types.Message):
    u = users[message.from_user.id]
    u["subject"] = message.text.replace("📐 ", "").replace("📜 ", "").replace("🧬 ", "").replace("🧪 ", "")
    u["step"] = "level"
    await message.answer("Выбери уровень", reply_markup=level_kb())

@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["База","Средний","Сложный"]))
async def start_ai(message: types.Message):
    u = users[message.from_user.id]
    u["step"] = "ai"

    text = ask_gpt(u)

    match = re.search(r"([ABCD])", text)
    if match:
        u["correct"] = match.group(1)

    text = re.sub(r"Правильный ответ.*", "", text)

    await message.answer(text, reply_markup=answer_kb())

# ===== ОТВЕТЫ (FIX) =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer_buttons(message: types.Message):
    u = users[message.from_user.id]

    if u["step"] != "ai":
        return

    user_answer = message.text

    if user_answer == u.get("correct"):

        u["correct_count"] = u.get("correct_count", 0) + 1
        await message.answer("✅ Правильно!")

    else:

        u["wrong_count"] = u.get("wrong_count", 0) + 1
        await message.answer(f"❌ Неправильно! Правильный ответ: {u.get('correct')}")

    explain = ask_gpt(u, "Объясни решение", mode="explain")
    await message.answer(explain)

    text = ask_gpt(u)

    match = re.search(r"([ABCD])", text)
    if match:
        u["correct"] = match.group(1)

    text = re.sub(r"Правильный ответ.*", "", text)

    await message.answer(text, reply_markup=answer_kb())

# ===== ЗАПУСК =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
