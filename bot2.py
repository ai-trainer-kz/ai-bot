import logging
import re
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

ADMIN_ID = 8398266271

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

user_data = {}
sessions = {}

# ================= СЕССИЯ =================
def get_user_session(uid):
    sessions.setdefault(uid, {
        "correct": 0,
        "wrong": 0,
        "total": 0,
        "topics": {},
        "mistakes": []
    })
    return sessions[uid]

# ================= КНОПКИ =================
def menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "📊 Статистика")
    kb.add("🧠 Тренажёр", "📖 Обучение")
    kb.add("💰 Оплата", "🌐 Тіл / Язык")
    return kb

def answers_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    return kb

# ================= СТАРТ =================
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("👋 Добро пожаловать!", reply_markup=menu())

# ================= ТРЕНАЖЁР =================
@dp.message_handler(lambda m: "тренаж" in m.text.lower())
async def trainer(message: types.Message):
    uid = str(message.from_user.id)
    user_data.setdefault(uid, {})
    user_data[uid]["mode"] = "trainer"

    await message.answer("🚀 Начинаем тест")
    await send_question(message)

# ================= ОБУЧЕНИЕ =================
@dp.message_handler(lambda m: "обуч" in m.text.lower())
async def learning(message: types.Message):
    uid = str(message.from_user.id)
    session = get_user_session(uid)

    if not session["topics"]:
        await message.answer("Нет слабых тем")
        return

    await message.answer("📚 Обучение")
    await send_question(message)

# ================= ВОПРОС =================
async def send_question(message):
    uid = str(message.from_user.id)
    subject = "математика"

    await message.answer("⏳ Генерирую вопрос...")

    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"""
Сделай 1 тестовый вопрос по предмету {subject}

Формат:

Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A/B/C/D
Объяснение: ...
"""
            }]
        )

        text = r.choices[0].message.content

    except Exception as e:
        await message.answer("❌ Ошибка генерации")
        print(e)
        return

    data = parse_question(text)

    user_data[uid] = data

    await message.answer(data["text"], reply_markup=answers_kb())

# ================= ПАРСИНГ =================
def parse_question(text):
    correct = re.search(r"Ответ:\s*([A-D])", text)
    explanation = re.search(r"Объяснение:\s*(.*)", text)

    return {
        "text": text.split("Ответ:")[0],
        "correct": correct.group(1) if correct else "A",
        "explanation": explanation.group(1) if explanation else ""
    }

# ================= ОТВЕТ =================
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    uid = str(message.from_user.id)
    data = user_data.get(uid)

    if not data:
        return

    session = get_user_session(uid)

    if message.text == data["correct"]:
        await message.answer("✅ Правильно")
        session["correct"] += 1
    else:
        await message.answer(f"❌ Неправильно\nОтвет: {data['correct']}")
        session["wrong"] += 1
        session["mistakes"].append(data)

    session["total"] += 1

    if data["explanation"]:
        await message.answer(f"📖 {data['explanation']}")

    if session["total"] % 5 == 0:
        percent = round((session["correct"]/session["total"])*100,1)
        await message.answer(f"📊 Результат: {percent}%")

    await send_question(message)

# ================= СТАТИСТИКА =================
@dp.message_handler(lambda m: "стат" in m.text.lower())
async def stats(message: types.Message):
    uid = str(message.from_user.id)
    session = get_user_session(uid)

    if session["total"] == 0:
        await message.answer("Нет данных")
        return

    percent = round((session["correct"]/session["total"])*100,1)
    await message.answer(f"📊 Результат: {percent}%")

# ================= ОПЛАТА =================
@dp.message_handler(lambda m: "оплата" in m.text.lower())
async def pay(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Я оплатил", "⬅️ Назад")

    await message.answer("Kaspi: 4400430352720152", reply_markup=kb)

@dp.message_handler(lambda m: "оплатил" in m.text.lower())
async def paid(message: types.Message):
    await bot.send_message(ADMIN_ID, f"💰 Оплата от {message.from_user.id}")
    await message.answer("⏳ Ожидайте подтверждения")

# ================= ЗАПУСК =================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
