import os
import json
import re

def clean_text(text):
    text = re.sub(r"\\\(|\\\)", "", text)
    text = re.sub(r"\\frac\{(.*?)\}\{(.*?)\}", r"\1/\2", text)
    text = text.replace("\\", "")
    return text

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

# ===== USERS =====
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def t(user_id, ru, kz):
    users = load_users()
    return kz if users.get(str(user_id), {}).get("lang") == "kz" else ru

# ===== KEYBOARDS =====
def main_menu(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "📊 Статистика")
    kb.add("🏆 Топ", "💳 Оплата")
    kb.add("🌐 Тіл / Язык")
    return kb

def subjects_kb(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    lang = load_users().get(str(user_id), {}).get("lang", "ru")

    if lang == "kz":
        kb.add("Математика", "Физика")
        kb.add("Биология", "Химия")
        kb.add("Тарих")
    else:
        kb.add("Математика", "Физика")
        kb.add("Биология", "Химия")
        kb.add("История")

    kb.add("⬅️ Назад")
    return kb

def answers_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B")
    kb.add("C","D")
    kb.add("⬅️ Назад")
    return kb

# ===== LANGUAGE =====
@dp.message_handler(lambda m: m.text == "🌐 Тіл / Язык")
async def choose_lang(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский","🇰🇿 Қазақша")
    kb.add("⬅️ Назад")
    await message.answer("Выбери язык / Тілді таңда", reply_markup=kb)

@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский","🇰🇿 Қазақша"])
async def set_lang(message: types.Message):
    users = load_users()
    uid = str(message.from_user.id)
    users.setdefault(uid, {})

    if "Русский" in message.text:
        users[uid]["lang"] = "ru"
        await message.answer("Язык установлен: Русский")
    else:
        users[uid]["lang"] = "kz"
        await message.answer("Тіл орнатылды: Қазақша")

    save_users(users)

# ===== AI =====
async def generate_question(subject, lang):
    language = "на русском языке" if lang == "ru" else "қазақ тілінде"

    prompt = f"""
Сгенерируй тест ЕНТ {language}

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

async def generate_explanation(question, correct, lang):
    language = "на русском языке" if lang == "ru" else "қазақ тілінде"

    prompt = f"""
Объясни решение {language}

{question}
"""

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

# ===== START =====
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("👋 Добро пожаловать!", reply_markup=main_menu(message.from_user.id))

# ===== MENU =====
@dp.message_handler(lambda m: m.text == "📚 Предметы")
async def subjects(message: types.Message):
    await message.answer(
        t(message.from_user.id,"Выбери предмет","Пәнді таңда"),
        reply_markup=subjects_kb(message.from_user.id)
    )

@dp.message_handler(lambda m: m.text in ["Математика","Физика","Биология","Химия","История","Тарих"])
async def subject_handler(message: types.Message):
    subject_map = {
        "Тарих":"История"
    }
    subject = subject_map.get(message.text, message.text)
    await send_question(message, subject)

# ===== QUESTION =====
async def send_question(message, subject):
    uid = str(message.from_user.id)
    users = load_users()

    users.setdefault(uid,{
        "used":0,
        "expire":"",
        "correct":0,
        "wrong":0,
        "name":message.from_user.full_name,
        "lang":"ru"
    })

    lang = users[uid]["lang"]

    if not users[uid]["expire"] and users[uid]["used"]>=10:
        await message.answer("💳 Лимит закончился")
        return

    users[uid]["used"]+=1
    save_users(users)

    msg = await message.answer("⏳ Генерирую...")

    raw = await generate_question(subject, lang)
    data = parse_question(raw)

    await msg.delete()

    question = re.sub(r"Ответ:.*","",data["text"],flags=re.DOTALL)
    question = re.sub(r"Объяснение:.*","",question,flags=re.DOTALL)

    user_data[uid]={
        "correct":data["correct"],
        "explanation":data["explanation"],
        "question":question,
        "subject":subject
    }

    await message.answer(question.strip(), reply_markup=answers_kb())

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def check_answer(message: types.Message):
    uid = str(message.from_user.id)
    answer = message.text

    data = user_data.get(uid,{})
    correct = data.get("correct")
    question = data.get("question")
    explanation = data.get("explanation")

    users = load_users()
    lang = users.get(uid,{}).get("lang","ru")

    if not explanation:
        explanation = await generate_explanation(question, correct, lang)

    users.setdefault(uid,{
        "used":0,
        "expire":"",
        "correct":0,
        "wrong":0,
        "name":message.from_user.full_name,
        "lang":"ru"
    })

    if answer==correct:
        await message.answer("✅ Правильно")
        users[uid]["correct"]+=1
    else:
        await message.answer(f"❌ Неправильно\nПравильный ответ: {correct}")
        users[uid]["wrong"]+=1

    save_users(users)

    await message.answer(f"📖 {clean_text(explanation)}\n\nПравильный ответ: {correct}")

    await send_question(message, data.get("subject","Математика"))

# ===== BACK =====
@dp.message_handler(lambda m: m.text=="⬅️ Назад")
async def back(message: types.Message):
    await message.answer("Меню", reply_markup=main_menu(message.from_user.id))

# ===== RUN =====
if __name__=="__main__":
    executor.start_polling(dp, skip_updates=True)
