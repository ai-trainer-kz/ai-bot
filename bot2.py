import os
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

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
    kb.add("📚 Предметы", "📊 Статистика")
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
    kb.add("A","B","C","D")
    kb.add("⬅️ Назад")
    return kb

def lang_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Русский", "Қазақша")
    return kb

# ===== УТИЛИТЫ =====

def get_user(uid):
    user_data.setdefault(uid, {
        "lang": "ru",
        "correct": 0,
        "wrong": 0
    })
    return user_data[uid]

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

# ===== НАЗАД =====

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
    user = get_user(uid)
    user["lang"] = "kz" if "Қазақша" in message.text else "ru"
    await message.answer("✅ OK", reply_markup=main_menu())

# ===== СТАТИСТИКА =====

@dp.message_handler(lambda m: "Статистика" in m.text)
async def stats(message: types.Message):
    uid = str(message.from_user.id)
    user = get_user(uid)

    total = user["correct"] + user["wrong"]
    percent = int((user["correct"]/total)*100) if total else 0

    text = f"""
📊 Статистика

✅ Правильно: {user['correct']}
❌ Неправильно: {user['wrong']}
🎯 Точность: {percent}%
"""
    await message.answer(text)

# ===== ПРЕДМЕТ =====

@dp.message_handler(lambda m: "Предмет" in m.text)
async def subjects(message: types.Message):
    await message.answer("Выбери предмет", reply_markup=subjects_kb())

@dp.message_handler(lambda m: m.text in ["Математика","История","География","Биология"])
async def subject(message: types.Message):
    uid = str(message.from_user.id)
    user = get_user(uid)
    user["subject"] = message.text
    await message.answer("Выбери сложность", reply_markup=level_kb())

# ===== УРОВЕНЬ =====

@dp.message_handler(lambda m: "Легкий" in m.text)
async def easy(message: types.Message):
    uid = str(message.from_user.id)
    get_user(uid)["level"] = "easy"
    await send_question(message)

@dp.message_handler(lambda m: "Сложный" in m.text)
async def hard(message: types.Message):
    uid = str(message.from_user.id)
    get_user(uid)["level"] = "hard"
    await send_question(message)

# ===== ГЕНЕРАЦИЯ =====

async def send_question(message: types.Message):
    uid = str(message.from_user.id)
    user = get_user(uid)

    subject = user.get("subject","Математика")
    level = user.get("level","easy")
    lang = user.get("lang","ru")

    msg = await message.answer("⏳ Генерация...")

    prompt = f"""
Ты — эксперт ЕНТ.

Сгенерируй 1 экзаменационный вопрос по предмету: {subject}
Сложность: {level}

ТРЕБОВАНИЯ:
- уровень как на настоящем ЕНТ
- НЕ простые вопросы
- 4 варианта
- только 1 правильный
- варианты должны быть похожи
- краткое объяснение

ФОРМАТ:

Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A
Объяснение: ...

Язык: {"казахский" if lang=="kz" else "русский"}
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role":"user","content":prompt}]
        )
        text = r.choices[0].message.content
    except Exception as e:
        print(e)
        await msg.edit_text("❌ Ошибка генерации")
        return

    await msg.delete()

    q = parse_question(text)

    user["correct_answer"] = q["correct"]
    user["expl"] = q["expl"]

    full = f"{q['q']}\n\n" + "\n".join(q["opts"])

    await message.answer(full, reply_markup=answers_kb())

# ===== ОТВЕТ =====

@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    uid = str(message.from_user.id)
    user = get_user(uid)

    if message.text == user.get("correct_answer"):
        user["correct"] += 1
        await message.answer("✅ Правильно!")
    else:
        user["wrong"] += 1
        await message.answer(f"❌ Неправильно. Ответ: {user.get('correct_answer')}")

    await message.answer(f"📖 {user.get('expl')}")

    await send_question(message)

# ===== ЗАПУСК =====

if __name__ == "__main__":
    if not API_TOKEN:
        print("❌ Нет BOT_TOKEN")
    else:
        executor.start_polling(dp, skip_updates=True)
