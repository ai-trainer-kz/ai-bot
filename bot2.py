import os
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from openai import OpenAI

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ADMINS = [8398266271]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

user_state = {}

FREE_LIMIT = 10

# ========= DB =========
if not os.path.exists("users.json"):
    with open("users.json", "w") as f:
        json.dump({}, f)

def load_users():
    with open("users.json", "r") as f:
        return json.load(f)

def save_users(data):
    with open("users.json", "w") as f:
        json.dump(data, f, indent=4)

def has_access(user_id):
    users = load_users()
    expire = users.get(str(user_id), {}).get("expire")

    if not expire:
        return False

    expire_date = datetime.strptime(expire, "%Y-%m-%d")
    return datetime.now() <= expire_date

# ========= AI =========
async def generate_question(subject):
    prompt = f"""
Ты AI-тренер для ЕНТ.

Сгенерируй 1 вопрос по предмету {subject}.

Формат строго:
Q: ...
A) ...
B) ...
C) ...
D) ...
ANSWER: A
EXPLAIN: ...
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=1
    )

    return response.choices[0].message.content


def parse_question(text):
    lines = text.split("\n")

    q, options, answer, explain = "", [], "", ""

    for line in lines:
        line = line.strip()

        if line.startswith("Q:"):
            q = line.replace("Q:", "").strip()
        elif line.startswith(("A)", "B)", "C)", "D)")):
            options.append(line)
        elif line.startswith("ANSWER:"):
            answer = line.replace("ANSWER:", "").strip()
        elif line.startswith("EXPLAIN:"):
            explain = line.replace("EXPLAIN:", "").strip()

    return q, options, answer, explain

# ========= KEYBOARD =========
def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B")
    kb.add("C", "D")
    kb.add("⬅️ Назад")
    return kb

# ========= SUBJECT =========
@dp.message_handler(lambda m: m.text in ["Математика", "Физика", "Биология", "История", "Химия"])
async def subject_handler(message: types.Message):

    user_id = str(message.from_user.id)
    subject = message.text

    users = load_users()
    users.setdefault(user_id, {"used": 0})

    if users[user_id]["used"] >= FREE_LIMIT and not has_access(user_id):
        await message.answer("🔒 Лимит достигнут\n💳 Оплатите доступ")
        return

    await message.answer("⏳ Генерирую вопрос...")

    text = await generate_question(subject)
    q, options, answer, explain = parse_question(text)

    if not q or len(options) < 4:
        await message.answer("⚠️ Ошибка генерации, попробуй ещё раз")
        return

    user_state[user_id] = {
        "answer": answer,
        "explain": explain,
        "subject": subject
    }

    await message.answer(q + "\n\n" + "\n".join(options), reply_markup=answer_kb())

# ========= ANSWER =========
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def check_answer(message: types.Message):

    user_id = str(message.from_user.id)

    if user_id not in user_state:
        await message.answer("Сначала выбери предмет")
        return

    correct = user_state[user_id]["answer"]
    explain = user_state[user_id]["explain"]
    subject = user_state[user_id]["subject"]

    if message.text == correct:
        await message.answer(f"✅ Правильно!\n\n📖 {explain}")
    else:
        await message.answer(f"❌ Неправильно\nОтвет: {correct}\n\n📖 {explain}")

    users = load_users()
    users.setdefault(user_id, {"used": 0})
    users[user_id]["used"] += 1
    save_users(users)

    if users[user_id]["used"] >= FREE_LIMIT and not has_access(user_id):
        await message.answer("🔒 Лимит достигнут\n💳 Оплатите доступ")
        return

    await message.answer("⏳ Следующий вопрос...")

    text = await generate_question(subject)
    q, options, answer, explain = parse_question(text)

    user_state[user_id] = {
        "answer": answer,
        "explain": explain,
        "subject": subject
    }

    await message.answer(q + "\n\n" + "\n".join(options), reply_markup=answer_kb())

# ========= RUN =========
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
