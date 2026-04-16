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

# ===== 💾 СОХРАНЕНИЕ =====
def save_users():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_users():
    global users
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            users.update(json.load(f))
    except:
        users = {}

# ===== USER =====
def ensure_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "step": "idle",
            "subject": None,
            "level": "Средний",
            "messages_used": 0,
            "correct": None,
            "history": [],
            "welcome_done": False  # ✅ ДОБАВИЛИ
        }
        save_users()

# ===== КНОПКИ =====
def main_kb(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Начать обучение")
    return kb

def subject_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📐 Математика", "📜 История")
    return kb

def level_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 База", "🟡 Средний", "🔴 Сложный")
    return kb

def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    return kb

# ===== GPT =====
def system_prompt(subject, level):
    return f"""
Ты преподаватель ЕНТ ({subject}), уровень {level}.

СОЗДАЙ:
1 вопрос + 4 варианта

ФОРМАТ:
Вопрос:
...
A) ...
B) ...
C) ...
D) ...

Правильный ответ:
A / B / C / D
"""

def ask_gpt(u, user_text=None, mode="question"):

    if mode == "question":
        system = system_prompt(u["subject"], u["level"])
    else:
        system = """
Ты объясняешь решение.

ЗАПРЕЩЕНО:
- писать "правильный ответ"
- писать буквы A/B/C/D

ТОЛЬКО объяснение.
"""

    messages = [{"role": "system", "content": system}]

    if user_text:
        messages.append({"role": "user", "content": user_text})
    else:
        messages.append({"role": "user", "content": "Начни тест"})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages
    )

    return resp.choices[0].message.content

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[message.from_user.id]

    if not u["welcome_done"]:
        await message.answer(
            "👋 Добро пожаловать в AI ЕНТ Тренер!\n\n"
            "📚 Выбери предмет\n"
            "🧠 Решай тесты\n"
            "🚀 Готовься к ЕНТ"
        )
        u["welcome_done"] = True
        save_users()

    await message.answer("Выбери действие:", reply_markup=main_kb(message.from_user.id))

# ===== ОБУЧЕНИЕ =====
@dp.message_handler(lambda m: m.text == "📚 Начать обучение")
async def choose_subject(message: types.Message):
    users[message.from_user.id]["step"] = "subject"
    await message.answer("Выбери предмет", reply_markup=subject_kb())

@dp.message_handler(lambda m: "Математика" in m.text or "История" in m.text)
async def choose_level(message: types.Message):
    u = users[message.from_user.id]
    u["subject"] = message.text
    u["step"] = "level"
    await message.answer("Выбери уровень", reply_markup=level_kb())

@dp.message_handler(lambda m: "База" in m.text or "Средний" in m.text or "Сложный" in m.text)
async def start_ai(message: types.Message):
    u = users[message.from_user.id]
    u["level"] = message.text
    u["step"] = "ai"

    text = ask_gpt(u, mode="question")

    match = re.search(r"Правильный ответ[:\s]*([ABCD])", text)
    if match:
        u["correct"] = match.group(1)

    text = re.sub(r"Правильный ответ[:\s]*[ABCD]", "", text)

    await message.answer(text, reply_markup=answer_kb())

# ===== ОТВЕТ =====
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def answer(message: types.Message):
    u = users[message.from_user.id]

    if u["step"] != "ai":
        return

    user_answer = message.text
    correct = u.get("correct")

    if user_answer == correct:
        result = "✅ Правильно!"
    else:
        result = f"❌ Неправильно! Правильный ответ: {correct}"

    explain = ask_gpt(
        u,
        f"Объясни решение задачи. Пользователь ответил {user_answer}",
        mode="explain"
    )

    await message.answer(result + "\n\n" + explain)

    # новый вопрос
    text = ask_gpt(u, mode="question")

    match = re.search(r"Правильный ответ[:\s]*([ABCD])", text)
    if match:
        u["correct"] = match.group(1)

    text = re.sub(r"Правильный ответ[:\s]*[ABCD]", "", text)

    await message.answer(text, reply_markup=answer_kb())

# ===== RUN =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
