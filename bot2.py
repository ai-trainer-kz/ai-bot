import os
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 8398266271

# цены/лимиты
FREE_MESSAGES = 10
PRICE_7 = "1000 тг"
PRICE_30 = "3000 тг"
KASPI = "87001234567"

# модель (можешь поменять при желании)
MODEL = "gpt-4o-mini"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

# ===== "БАЗА" (в памяти, без падений) =====
users = {}

# ===== КНОПКИ =====
def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Начать обучение")
    kb.add("💰 Доступ", "📊 Статус")
    return kb

def subject_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "История")
    kb.add("Биология", "Английский")
    kb.add("Назад")
    return kb

def level_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("База", "Средний", "Сложный")
    kb.add("Назад")
    return kb

def pay_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 Оплатил")
    kb.add("Назад")
    return kb

# ===== УТИЛИТЫ =====
def ensure_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "step": "idle",
            "subject": None,
            "level": None,
            "messages_used": 0,
            "premium_until": None,
            "history": []  # диалог с GPT
        }

def has_access(u):
    if u["premium_until"] and datetime.now() < u["premium_until"]:
        return True
    return False

def can_use(u):
    if has_access(u):
        return True
    return u["messages_used"] < FREE_MESSAGES

def system_prompt(subject, level):
    return f"""
Ты — строгий, но понятный преподаватель ЕНТ по предмету: {subject}.
Уровень ученика: {level}.

Твоя задача:
1) Задавать по одному вопросу за раз (ЕНТ формат: тест/задача/теория).
2) После ответа ученика:
   - сказать правильно или нет
   - дать КОРОТКОЕ объяснение (2–4 предложения)
   - если ошибка — показать правильный путь решения
3) Затем задать следующий вопрос.
4) Пиши на русском, чётко и без воды.

Не задавай слишком лёгкие вопросы вроде "2+2".
Держи уровень, соответствующий ЕНТ.
"""

def ask_gpt(u, user_text=None):
    messages = []

    # system
    messages.append({"role": "system", "content": system_prompt(u["subject"], u["level"])})

    # история
    messages.extend(u["history"][-10:])

    # если первый раз — пусть сам задаст вопрос
    if not user_text:
        messages.append({"role": "user", "content": "Начни занятие. Задай первый вопрос."})
    else:
        messages.append({"role": "user", "content": user_text})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.6,
    )

    answer = resp.choices[0].message.content

    # сохраняем в историю
    if user_text:
        u["history"].append({"role": "user", "content": user_text})
    u["history"].append({"role": "assistant", "content": answer})

    return answer

# ===== СТАРТ =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    await message.answer(
        "🤖 AI ЕНТ Тренер\n\nНажми «Начать обучение»",
        reply_markup=main_kb()
    )

# ===== НАЧАТЬ =====
@dp.message_handler(lambda m: m.text == "📚 Начать обучение")
async def choose_subject(message: types.Message):
    ensure_user(message.from_user.id)
    users[message.from_user.id]["step"] = "subject"
    await message.answer("Выбери предмет", reply_markup=subject_kb())

@dp.message_handler(lambda m: m.text in ["Математика", "История", "Биология", "Английский"])
async def choose_level(message: types.Message):
    u = users[message.from_user.id]
    u["subject"] = message.text
    u["step"] = "level"
    await message.answer("Выбери уровень", reply_markup=level_kb())

@dp.message_handler(lambda m: m.text in ["База", "Средний", "Сложный"])
async def start_ai(message: types.Message):
    u = users[message.from_user.id]
    u["level"] = message.text
    u["step"] = "ai"
    u["history"] = []

    if not can_use(u):
        await message.answer(
            f"❌ Лимит закончился\n\nKaspi: {KASPI}\n7 дней — {PRICE_7}\n30 дней — {PRICE_30}",
            reply_markup=pay_kb()
        )
        return

    text = ask_gpt(u)
    await message.answer(text)

# ===== ОСНОВНОЙ AI ДИАЛОГ =====
@dp.message_handler(lambda m: True)
async def ai_chat(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[message.from_user.id]

    # навигация
    if message.text == "Назад":
        u["step"] = "idle"
        await message.answer("Главное меню", reply_markup=main_kb())
        return

    if message.text == "💰 Доступ":
        await message.answer(
            f"Kaspi: {KASPI}\n7 дней — {PRICE_7}\n30 дней — {PRICE_30}",
            reply_markup=pay_kb()
        )
        return

    if message.text == "📊 Статус":
        status = "Премиум" if has_access(u) else "Бесплатный"
        await message.answer(
            f"Статус: {status}\nИспользовано: {u['messages_used']}/{FREE_MESSAGES}"
        )
        return

    if message.text == "💰 Оплатил":
        await bot.send_message(
            ADMIN_ID,
            f"Оплата от {message.from_user.id} @{message.from_user.username}"
        )
        await message.answer("⏳ Проверяем оплату")
        return

    # если не в режиме AI — игнор
    if u["step"] != "ai":
        return

    if not can_use(u):
        await message.answer(
            f"❌ Лимит закончился\n\nKaspi: {KASPI}\n7 дней — {PRICE_7}\n30 дней — {PRICE_30}",
            reply_markup=pay_kb()
        )
        return

    # считаем сообщение
    if not has_access(u):
        u["messages_used"] += 1

    answer = ask_gpt(u, message.text)
    await message.answer(answer)

# ===== АДМИН ВЫДАЁТ ДОСТУП =====
@dp.message_handler(commands=['give7'])
async def give7(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    user_id = int(message.get_args())
    ensure_user(user_id)
    users[user_id]["premium_until"] = datetime.now() + timedelta(days=7)
    await message.answer("Дал 7 дней")

@dp.message_handler(commands=['give30'])
async def give30(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    user_id = int(message.get_args())
    ensure_user(user_id)
    users[user_id]["premium_until"] = datetime.now() + timedelta(days=30)
    await message.answer("Дал 30 дней")

# ===== ЗАПУСК =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
