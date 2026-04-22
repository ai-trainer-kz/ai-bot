import os
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from openai import OpenAI

# ===== НАСТРОЙКИ =====
API_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_data = {}

# ===== КНОПКИ =====

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы")
    kb.add("🌐 Язык")
    return kb

def subjects_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "История")
    kb.add("География", "Биология")
    kb.add("⬅️ Назад")
    return kb

def level_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Легкий", "🔴 Сложный")
    kb.add("⬅️ Назад")
    return kb

def answers_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    kb.add("⬅️ Назад")
    return kb

def lang_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Русский", "Қазақша")
    return kb

# ===== УТИЛИТЫ =====

def get_lang(uid):
    return user_data.get(uid, {}).get("lang", "ru")

def parse_question(text):
    lines = text.split("\n")

    q = ""
    opts = []

    for l in lines:
        if "Вопрос" in l:
            q = l
        if re.match(r"[A-D]\)", l.strip()):
            opts.append(l.strip())

    correct = re.search(r"Ответ:\s*([A-D])", text)
    expl = re.search(r"Объяснение:\s*(.+)", text, re.DOTALL)

    return {
        "q": q,
        "opts": opts,
        "correct": correct.group(1) if correct else "A",
        "expl": expl.group(1).strip() if expl else ""
    }

# ===== СТАРТ =====

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("👋 Добро пожаловать!", reply_markup=main_menu())

# ===== НАЗАД (ГЛОБАЛЬНЫЙ) =====

@dp.message_handler(lambda m: "Назад" in m.text)
async def back(message: types.Message):
    await message.answer("Меню", reply_markup=main_menu())

# ===== ЯЗЫК =====

@dp.message_handler(lambda m: "Язык" in m.text)
async def choose_lang(message: types.Message):
    await message.answer("Выбери язык", reply_markup=lang_kb())

@dp.message_handler(lambda m: m.text in ["Русский", "Қазақша"])
async def set_lang(message: types.Message):
    uid = str(message.from_user.id)
    user_data.setdefault(uid, {})
    user_data[uid]["lang"] = "kz" if "Қазақша" in message.text else "ru"
    await message.answer("✅ OK", reply_markup=main_menu())

# ===== ПРЕДМЕТЫ =====

@dp.message_handler(lambda m: "Предмет" in m.text)
async def subjects(message: types.Message):
    await message.answer("Выбери предмет", reply_markup=subjects_kb())

@dp.message_handler(lambda m: m.text in ["Математика", "История", "География", "Биология"])
async def subject(message: types.Message):
    uid = str(message.from_user.id)
    user_data.setdefault(uid, {})
    user_data[uid]["subject"] = message.text
    await message.answer("Выбери сложность", reply_markup=level_kb())

# ===== УРОВЕНЬ =====

@dp.message_handler(lambda m: "Легкий" in m.text)
async def easy(message: types.Message):
    uid = str(message.from_user.id)
    user_data[uid]["level"] = "easy"
    await send_question(message)

@dp.message_handler(lambda m: "Сложный" in m.text)
async def hard(message: types.Message):
    uid = str(message.from_user.id)
    user_data[uid]["level"] = "hard"
    await send_question(message)

# ===== ГЕНЕРАЦИЯ =====

async def send_question(message: types.Message):
    uid = str(message.from_user.id)
    data = user_data.get(uid, {})

    subject = data.get("subject", "Математика")
    level = data.get("level", "easy")
    lang = get_lang(uid)

    msg = await message.answer("⏳ Генерация...")

    try:
        prompt = f"""
Сделай тестовый вопрос по предмету: {subject}
Сложность: {level}

Формат строго:
Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A
Объяснение: ...

Язык: {"казахский" if lang=="kz" else "русский"}
"""

        r = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        text = r.choices[0].message.content

    except Exception as e:
        print("ERROR:", e)
        await msg.edit_text("❌ Ошибка генерации")
        return

    await msg.delete()

    q = parse_question(text)

    user_data[uid]["correct"] = q["correct"]
    user_data[uid]["expl"] = q["expl"]

    full_text = f"{q['q']}\n\n" + "\n".join(q["opts"])

    await message.answer(full_text, reply_markup=answers_kb())

# ===== ОТВЕТ =====

@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def answer(message: types.Message):
    uid = str(message.from_user.id)
    data = user_data.get(uid, {})

    if message.text == data.get("correct"):
        await message.answer("✅ Правильно!")
    else:
        await message.answer(f"❌ Неправильно. Ответ: {data.get('correct')}")

    await message.answer(f"📖 {data.get('expl')}")

    # следующий вопрос автоматически
    await send_question(message)

# ===== ЗАПУСК =====

if __name__ == "__main__":
    if not API_TOKEN:
        print("❌ BOT_TOKEN не найден")
    else:
        executor.start_polling(dp, skip_updates=True)
