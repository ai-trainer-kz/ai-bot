import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from openai import OpenAI

API_TOKEN = "ТВОЙ_ТОКЕН_БОТА"
client = OpenAI(api_key="ТВОЙ_OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_data = {}

# ===== КНОПКИ =====

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы")
    kb.add("🌐 Тіл / Язык")
    return kb

def subjects_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "История")
    kb.add("⬅️ Назад")
    return kb

def level_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Легкий", "🔴 Сложный")
    kb.add("🟢 Жеңіл", "🔴 Қиын")
    kb.add("⬅️ Назад")
    return kb

def answers_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    return kb

def lang_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Русский", "Қазақша")
    return kb

# ===== ВСПОМОГАТЕЛЬНЫЕ =====

def get_lang(uid):
    return user_data.get(uid, {}).get("lang", "ru")

def extract_answer(text):
    m = re.search(r"Ответ:\s*([A-D])", text)
    return m.group(1) if m else "A"

def extract_explanation(text):
    m = re.search(r"Объяснение:\s*(.+)", text, re.DOTALL)
    return m.group(1).strip() if m else "Нет объяснения"

def clean_question(text):
    text = re.sub(r"Ответ:.*", "", text, flags=re.DOTALL)
    text = re.sub(r"Объяснение:.*", "", text, flags=re.DOTALL)
    return text.strip()

# ===== СТАРТ =====

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("👋 Добро пожаловать!", reply_markup=main_menu())

# ===== ЯЗЫК =====

@dp.message_handler(lambda m: "Язык" in m.text or "Тіл" in m.text)
async def choose_lang(message: types.Message):
    await message.answer("Выбери язык", reply_markup=lang_kb())

@dp.message_handler(lambda m: m.text in ["Русский", "Қазақша"])
async def set_lang(message: types.Message):
    uid = str(message.from_user.id)
    user_data.setdefault(uid, {})
    user_data[uid]["lang"] = "kz" if "Қазақша" in message.text else "ru"
    await message.answer("✅ OK", reply_markup=main_menu())

# ===== ПРЕДМЕТ =====

@dp.message_handler(lambda m: "Предмет" in m.text)
async def subjects(message: types.Message):
    await message.answer("Выбери предмет", reply_markup=subjects_kb())

@dp.message_handler(lambda m: m.text in ["Математика", "История"])
async def subject_chosen(message: types.Message):
    uid = str(message.from_user.id)
    user_data.setdefault(uid, {})
    user_data[uid]["subject"] = message.text
    await message.answer("Выбери сложность", reply_markup=level_kb())

# ===== УРОВЕНЬ =====

@dp.message_handler(lambda m: "Легкий" in m.text or "Жеңіл" in m.text)
async def easy(message: types.Message):
    uid = str(message.from_user.id)
    user_data.setdefault(uid, {})
    user_data[uid]["level"] = "easy"
    await send_question(message)

@dp.message_handler(lambda m: "Сложный" in m.text or "Қиын" in m.text)
async def hard(message: types.Message):
    uid = str(message.from_user.id)
    user_data.setdefault(uid, {})
    user_data[uid]["level"] = "hard"
    await send_question(message)

# ===== ГЕНЕРАЦИЯ =====

async def send_question(message: types.Message):
    uid = str(message.from_user.id)
    data = user_data.get(uid, {})

    subject = data.get("subject", "Математика")
    level = data.get("level", "easy")
    lang = get_lang(uid)

    msg = await message.answer("⏳ Генерирую...")

    try:
        prompt = f"""
Сделай 1 тестовый вопрос по предмету {subject}.
Сложность: {level}

Формат:
Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A
Объяснение: ...

Язык: {"казахский" if lang == "kz" else "русский"}
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

    user_data[uid]["correct"] = extract_answer(text)
    user_data[uid]["explanation"] = extract_explanation(text)

    question = clean_question(text)

    await message.answer(question, reply_markup=answers_kb())

# ===== ОТВЕТ =====

@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def answer(message: types.Message):
    uid = str(message.from_user.id)
    data = user_data.get(uid, {})

    if not data:
        return

    if message.text == data.get("correct"):
        await message.answer("✅ Правильно!")
    else:
        await message.answer(f"❌ Неправильно! Ответ: {data.get('correct')}")

    await message.answer(f"📖 {data.get('explanation')}")

# ===== НАЗАД =====

@dp.message_handler(lambda m: "Назад" in m.text)
async def back(message: types.Message):
    await message.answer("Меню", reply_markup=main_menu())

# ===== СТАРТ БОТА =====

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
