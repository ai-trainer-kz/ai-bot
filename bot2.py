import os
import json
import re
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

ADMIN_ID = 8398266271

USERS_FILE = "users.json"
user_data = {}

# ===== UTILS =====
def clean_text(text):
    text = re.sub(r"\\\(|\\\)", "", text)
    text = re.sub(r"\\frac\{(.*?)\}\{(.*?)\}", r"\1/\2", text)
    text = text.replace("\\", "")
    return text

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def get_lang(user_id):
    users = load_users()
    return users.get(str(user_id), {}).get("lang", "ru")

# ===== KEYBOARDS =====
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "📊 Статистика")
    kb.add("🏆 Топ", "💳 Оплата")
    kb.add("🌐 Тіл / Язык")
    return kb

def subjects_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "Физика")
    kb.add("Биология", "Химия")
    kb.add("История", "Тарих")
    kb.add("⬅️ Назад")
    return kb

def answers_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B")
    kb.add("C", "D")
    kb.add("⬅️ Назад")
    return kb

# ===== START =====
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("👋 Добро пожаловать!", reply_markup=main_menu())

# ===== LANGUAGE =====
@dp.message_handler(lambda m: m.text == "🌐 Тіл / Язык")
async def lang_menu(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")
    kb.add("⬅️ Назад")
    await message.answer("Выбери язык / Тілді таңда", reply_markup=kb)

@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def set_lang(message: types.Message):
    users = load_users()
    uid = str(message.from_user.id)

    users.setdefault(uid, {})

    users[uid]["lang"] = "ru" if "Русский" in message.text else "kz"

    save_users(users)

    await message.answer("✅ Язык сохранен", reply_markup=main_menu())

# ===== SUBJECT =====
@dp.message_handler(lambda m: m.text == "📚 Предметы")
async def subjects(message: types.Message):
    await message.answer("Выбери предмет", reply_markup=subjects_kb())

@dp.message_handler(lambda m: m.text in ["Математика","Физика","Биология","Химия","История","Тарих"])
async def subject_handler(message: types.Message):
    subject = "История" if message.text == "Тарих" else message.text
    await send_question(message, subject)

# ===== AI =====
async def generate_question(subject, lang):
    lang_text = "на русском языке" if lang == "ru" else "қазақ тілінде"

    prompt = f"""
Сгенерируй тест ЕНТ {lang_text}

Предмет: {subject}

Формат:
Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A/B/C/D
Объяснение: ...
"""

    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role":"user","content":prompt}]
    )
    return r.choices[0].message.content

async def generate_explanation(question, lang):
    lang_text = "на русском языке" if lang == "ru" else "қазақ тілінде"

    prompt = f"Объясни решение {lang_text}\n{question}"

    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role":"user","content":prompt}]
    )
    return r.choices[0].message.content

def parse_question(text):
    correct = re.search(r"Ответ:\s*([A-D])", text)
    explanation = re.search(r"Объяснение:\s*(.*)", text)

    return {
        "text": clean_text(text),
        "correct": correct.group(1) if correct else "A",
        "explanation": clean_text(explanation.group(1)) if explanation else ""
    }

# ===== QUESTION =====
async def send_question(message, subject):
    uid = str(message.from_user.id)
    users = load_users()

    users.setdefault(uid, {
        "used": 0,
        "expire": "",
        "correct": 0,
        "wrong": 0,
        "name": message.from_user.full_name,
        "lang": "ru"
    })

    if not users[uid]["expire"] and users[uid]["used"] >= 10:
        await message.answer("💳 Лимит закончился")
        return

    users[uid]["used"] += 1
    save_users(users)

    msg = await message.answer("⏳ Генерирую...")

    raw = await generate_question(subject, users[uid]["lang"])
    data = parse_question(raw)

    await msg.delete()

    question = re.sub(r"Ответ:.*", "", data["text"], flags=re.DOTALL)
    question = re.sub(r"Объяснение:.*", "", question, flags=re.DOTALL)

    user_data[uid] = {
        "correct": data["correct"],
        "question": question,
        "explanation": data["explanation"],
        "subject": subject
    }

    await message.answer(question.strip(), reply_markup=answers_kb())

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def check_answer(message: types.Message):
    uid = str(message.from_user.id)
    data = user_data.get(uid)

    if not data:
        await message.answer("Сначала выбери предмет")
        return

    users = load_users()

    users.setdefault(uid, {
        "used": 0,
        "expire": "",
        "correct": 0,
        "wrong": 0,
        "name": message.from_user.full_name,
        "lang": "ru"
    })

    if message.text == data["correct"]:
        await message.answer("✅ Правильно")
        users[uid]["correct"] += 1
    else:
        await message.answer(f"❌ Неправильно\nПравильный ответ: {data['correct']}")
        users[uid]["wrong"] += 1

    save_users(users)

    explanation = data["explanation"] or await generate_explanation(data["question"], users[uid]["lang"])

    await message.answer(f"📖 {clean_text(explanation)}")

    await send_question(message, data["subject"])

# ===== STATS =====
@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def stats(message: types.Message):
    users = load_users()
    u = users.get(str(message.from_user.id), {})

    c = u.get("correct",0)
    w = u.get("wrong",0)
    total = c + w
    acc = round((c/total)*100,1) if total else 0

    await message.answer(f"📊\n✅ {c}\n❌ {w}\n📚 {total}\n🎯 {acc}%")

# ===== TOP =====
@dp.message_handler(lambda m: m.text == "🏆 Топ")
async def top(message: types.Message):
    users = load_users()

    rating = []
    for u in users.values():
        c = u.get("correct",0)
        w = u.get("wrong",0)
        total = c+w
        if total>0:
            rating.append((u.get("name","User"), c, c/total))

    rating.sort(key=lambda x:x[2], reverse=True)

    text = "🏆 Топ:\n"
    for i,(n,c,a) in enumerate(rating[:10],1):
        text += f"{i}. {n} — {c} ({round(a*100)}%)\n"

    await message.answer(text)

# ===== PAYMENT =====
@dp.message_handler(lambda m: m.text == "💳 Оплата")
async def payment(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Я оплатил")
    kb.add("⬅️ Назад")

    await message.answer("Kaspi: 4400430352720152", reply_markup=kb)

@dp.message_handler(lambda m: "оплатил" in m.text.lower())
async def paid(message: types.Message):
    await bot.send_message(ADMIN_ID, f"Оплата от {message.from_user.id}")

# ===== BACK =====
@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def back(message: types.Message):
    await message.answer("Меню", reply_markup=main_menu())

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
