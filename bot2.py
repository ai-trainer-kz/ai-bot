import os
import logging
import json
from datetime import datetime, timedelta

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
        if u["premium_until"]:
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
                if users[uid]["premium_until"]:
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

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📋 Пользователи")
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
            "wrong": 0,
            "paid": False,
            "created_at": datetime.now().isoformat()
        }
        save_users()

def has_access(u):
    return u["premium_until"] and datetime.now() < u["premium_until"]

def can_use(u):
    return has_access(u) or u["messages_used"] < FREE_MESSAGES

# ===== GPT =====
def system_prompt(subject, level, lang):
    if lang == "kz":
        return f"""
Сен ҰБТ мұғалімі ({subject}). Деңгей: {level}.

ТЕК тест жаса.

МАЗМҰН:
- ТЕК 1 сұрақ
- 4 жауап нұсқасы

ТЫЙЫМ:
- LaTeX қолданба

ФОРМАТ:
Сұрақ:
...
A) ...
B) ...
C) ...
D) ...

ДҰРЫС ЖАУАП:
A / B / C / D
"""
    return f"""
Ты преподаватель ЕНТ ({subject}). Уровень: {level}.

СОЗДАЙ ТОЛЬКО ТЕСТ.

ТРЕБОВАНИЯ:
- Только 1 вопрос
- 4 варианта ответа

ЗАПРЕЩЕНО:
- НЕ используй LaTeX

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

def ask_gpt(u, user_text=None):
    messages = [{"role": "system", "content": system_prompt(u["subject"], u["level"], u["lang"])}]
    messages += u["history"][-10:]

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

    if user_text:
        u["history"].append({"role": "user", "content": user_text})
    u["history"].append({"role": "assistant", "content": answer})

    save_users()
    return answer

# ===== СТАРТ =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    await message.answer("🤖 AI ЕНТ Тренер", reply_markup=main_kb(message.from_user.id))

# ===== ОБУЧЕНИЕ =====
@dp.message_handler(lambda m: m.text == "📚 Начать обучение")
async def choose_subject(message: types.Message):
    ensure_user(message.from_user.id)
    users[message.from_user.id]["step"] = "subject"
    save_users()
    await message.answer("Выбери предмет", reply_markup=subject_kb())

@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["Математика","История","Биология","Химия"]))
async def choose_level(message: types.Message):
    u = users[message.from_user.id]
    u["subject"] = message.text
    u["step"] = "level"
    save_users()
    await message.answer("Выбери уровень", reply_markup=level_kb())

@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["База","Средний","Сложный"]))
async def start_ai(message: types.Message):
    u = users[message.from_user.id]
    u["level"] = message.text
    u["step"] = "ai"
    u["history"] = []
    save_users()

    if not can_use(u):
        await message.answer(f"❌ Лимит\nKaspi: {KASPI}", reply_markup=pay_kb())
        return

    text = ask_gpt(u)

    import re
    match = re.search(r"Правильный ответ[:\s]*([ABCD])", text)
    if match:
        u["correct"] = match.group(1)

    text = re.sub(r"Правильный ответ[:\s]*[ABCD]", "", text)

    await message.answer(text, reply_markup=answer_kb())

# ===== НАЗАД =====
@dp.message_handler(lambda m: "Назад" in m.text)
async def go_back(message: types.Message):
    u = users[message.from_user.id]

    u["step"] = "subject"
    save_users()

    await message.answer("⬅️ Назад\n\nВыбери предмет:", reply_markup=subject_kb())
# ===== ОТВЕТЫ =====
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def answer_buttons(message: types.Message):
    u = users[message.from_user.id]

    if u["step"] != "ai":
        return

    user_answer = message.text
    correct = u.get("correct")

    if not correct:
        await message.answer("Ошибка. Попробуй ещё раз.")
        return

    if user_answer == correct:
        result = "✅ Правильно!"
    else:
        result = f"❌ Неправильно! Правильный ответ: {correct}"

    explain = ask_gpt(u, f"Объясни коротко, почему правильный ответ {correct}")

    await message.answer(result + "\n\n" + explain)

    text = ask_gpt(u)

    import re
    match = re.search(r"Правильный ответ[:\s]*([ABCD])", text)
    if match:
        u["correct"] = match.group(1)

    text = re.sub(r"Правильный ответ[:\s]*[ABCD]", "", text)

    await message.answer(text, reply_markup=answer_kb())

# ===== ЗАПУСК =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
