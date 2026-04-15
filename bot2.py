import os
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 8398266271

FREE_MESSAGES = 10
PRICE_7 = "1000 тг"
PRICE_30 = "3000 тг"
KASPI = "87001234567"

MODEL = "gpt-4o-mini"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

users = {}

# ===== КНОПКИ =====
def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Начать обучение")
    kb.add("💰 Купить доступ", "📊 Статус")
    kb.add("🌐 Язык")
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
            "correct": 0,
            "wrong": 0
        }

def has_access(u):
    return u["premium_until"] and datetime.now() < u["premium_until"]

def can_use(u):
    return has_access(u) or u["messages_used"] < FREE_MESSAGES

def adapt_level(u):
    if u["correct"] >= 3:
        return "Сложный"
    elif u["wrong"] >= 3:
        return "База"
    return "Средний"

def system_prompt(subject, level, lang):
    language = "русском языке" if lang == "ru" else "казахском языке"

    return f"""
Ты — преподаватель ЕНТ по предмету: {subject}.
Говори только на {language} языке.

Сначала задай вопрос с вариантами A B C D.
Не показывай ответ.
После ответа ученика:
- скажи правильно или нет
- покажи правильный ответ
- коротко объясни
- задай следующий вопрос
"""

def ask_gpt(u, user_text=None):
    level = adapt_level(u)

    messages = [
        {"role": "system", "content": system_prompt(u["subject"], level, u["lang"])}
    ]

    messages += u["history"][-10:]

    if not user_text:
        messages.append({"role": "user", "content": "Начни тест"})
    else:
        messages.append({"role": "user", "content": user_text})

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.6,
        )
        answer = resp.choices[0].message.content
    except Exception as e:
        print("GPT ERROR:", e)
        return "❌ Ошибка GPT"

    if user_text:
        u["history"].append({"role": "user", "content": user_text})
    u["history"].append({"role": "assistant", "content": answer})

    return answer

# ===== СТАРТ =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    await message.answer("🤖 AI ЕНТ Тренер", reply_markup=main_kb())

# ===== ОБУЧЕНИЕ =====
@dp.message_handler(lambda m: m.text == "📚 Начать обучение")
async def choose_subject(message: types.Message):
    users[message.from_user.id]["step"] = "subject"
    await message.answer("Выбери предмет", reply_markup=subject_kb())

@dp.message_handler(lambda m: any(x in m.text for x in ["Математика","История","Биология","Химия"]))
async def choose_level(message: types.Message):
    u = users[message.from_user.id]
    u["subject"] = message.text.replace("📐 ","").replace("📜 ","").replace("🧬 ","").replace("🧪 ","")
    u["step"] = "level"
    await message.answer("Выбери уровень", reply_markup=level_kb())

@dp.message_handler(lambda m: any(x in m.text for x in ["База","Средний","Сложный"]))
async def start_ai(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[message.from_user.id]

    text = message.text.replace("🟢","").replace("🟡","").replace("🔴","").strip()

    u["level"] = text
    u["step"] = "ai"
    u["history"] = []

    if not can_use(u):
        await message.answer(
            f"❌ Лимит закончился\n\nKaspi: {KASPI}\n7 дней — {PRICE_7}\n30 дней — {PRICE_30}",
            reply_markup=pay_kb()
        )
        return

    await message.answer(ask_gpt(u), reply_markup=answer_kb())

# ===== ЧАТ =====
@dp.message_handler(lambda m: True)
async def ai_chat(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[message.from_user.id]

    if u["step"] != "ai":
        return

    if not can_use(u):
        await message.answer(
            f"❌ Лимит закончился\n\nKaspi: {KASPI}\n7 дней — {PRICE_7}\n30 дней — {PRICE_30}",
            reply_markup=pay_kb()
        )
        return

    if not has_access(u):
        u["messages_used"] += 1

    await message.answer(ask_gpt(u, message.text), reply_markup=answer_kb())

# ===== ОСТАЛЬНОЕ НЕ ТРОГАЛ =====
# (оплата, статус, админ — 그대로)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
