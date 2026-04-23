import os
import json
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

API_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

DATA_FILE = "users.json"

# 🔥 ДОБАВИЛ
ADMIN_ID = 8398266271
KASPI = "4400430352720152"
LIMIT = 30

client = OpenAI(api_key=OPENAI_KEY)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ===== STORAGE =====

def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users = load_users()

def get_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {
            "lang": "ru",
            "subject": None,
            "topic": None,
            "level": "easy",
            "correct": 0,
            "wrong": 0,
            "history": [],
            "last_q": None,
            "busy": False,
            "paid": False
        }
    return users[uid]

# ===== UI =====

def t(u, ru, kz):
    return kz if u.get("lang") == "kz" else ru

def kb_main(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы","🧠 Тренировка")
    kb.add("📊 Статистика","🌐 Язык")
    return kb

def kb_subjects(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика","История")
    kb.add("География","Биология")
    kb.add("⬅️ Назад")
    return kb

def kb_topics(subject):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    data = {
        "Математика": ["Алгебра","Геометрия","Проценты","Логарифмы"],
        "История": ["Казахстан","Мировая","Даты","Персоны"],
        "География": ["Климат","Страны","Ресурсы","Карты"],
        "Биология": ["Клетка","Генетика","Анатомия","Экология"]
    }
    for tpc in data.get(subject, []):
        kb.add(tpc)
    kb.add("⬅️ Назад")
    return kb

def kb_level():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Легкий","🟡 Средний","🔴 Сложный")
    kb.add("⬅️ Назад")
    return kb

def kb_answers():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    kb.add("⬅️ Назад")
    return kb

def kb_lang():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Русский","Қазақша")
    kb.add("⬅️ Назад")
    return kb

# ===== HELPERS =====

def clean(text):
    if not text:
        return ""
    text = re.sub(r"\\frac\{(.+?)\}\{(.+?)\}", r"(\1/\2)", text)
    return text.strip()

def parse(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    opts = [l for l in lines if re.match(r"^[A-D]\)", l)]

    correct_match = re.search(r"(Ответ|Жауап)\s*:\s*([A-D])", text)
    correct_letter = correct_match.group(2) if correct_match else None

    return {
        "q": lines[0] if lines else "",
        "opts": opts[:4],
        "correct": correct_letter,
        "expl": ""
    }

# ===== AI =====

def build_prompt(u):
    return f"""
Предмет: {u['subject']}
Тема: {u['topic']}

НЕ смешивай предметы!

Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A
"""

async def gen(u):
    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": build_prompt(u)}]
    )
    return parse(r.choices[0].message.content)

# ===== LOGIC =====

async def check_limit(m, u):
    total = u["correct"] + u["wrong"]

    if not u["paid"] and total >= LIMIT:
        await m.answer(
            f"🚫 Лимит достигнут!\n\n"
            f"💳 Оплата: 7.30\n"
            f"KASPI: {KASPI}\n\n"
            f"После оплаты нажми: Я оплатил"
        )
        return True
    return False

@dp.message_handler(lambda m: m.text == "Я оплатил")
async def paid(m):
    u = get_user(m.from_user.id)

    await bot.send_message(
        ADMIN_ID,
        f"Оплата от @{m.from_user.username} | {m.from_user.id}"
    )

    await m.answer("⏳ Ожидайте подтверждения")
    
@dp.message_handler(commands=["start"])
async def start(m):
    u = get_user(m.from_user.id)
    await m.answer("Добро пожаловать", reply_markup=kb_main(u))

@dp.message_handler(lambda m: "Предмет" in m.text)
async def subjects(m):
    u = get_user(m.from_user.id)
    await m.answer("Выбери предмет", reply_markup=kb_subjects(u))

@dp.message_handler(lambda m: m.text in ["Математика","История","География","Биология"])
async def set_sub(m):
    u = get_user(m.from_user.id)
    u["subject"] = m.text
    u["topic"] = None
    save_users(users)
    await m.answer("Выбери тему", reply_markup=kb_topics(m.text))

@dp.message_handler(lambda m: m.text in [
"Алгебра","Геометрия","Проценты","Логарифмы",
"Казахстан","Мировая","Даты","Персоны",
"Климат","Страны","Ресурсы","Карты",
"Клетка","Генетика","Анатомия","Экология"])
async def set_topic(m):
    u = get_user(m.from_user.id)
    u["topic"] = m.text
    save_users(users)
    await ask(m)

async def ask(m):
    u = get_user(m.from_user.id)

    if await check_limit(m, u):
        return

    q = await gen(u)

    u["last_q"] = q
    save_users(users)

    text = f"{q['q']}\n\n" + "\n".join(q["opts"])
    await m.answer(text, reply_markup=kb_answers())

@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def ans(m):
    u = get_user(m.from_user.id)
    q = u.get("last_q")

    if not q:
        return

    correct = q.get("correct")

    if not correct:
        await m.answer("⚠️ Ошибка в вопросе (нет правильного ответа)")
        return

    ok = m.text == correct

    if ok:
        u["correct"] += 1
        await m.answer("✅ Правильно")
    else:
        u["wrong"] += 1
        await m.answer(f"❌ Правильный ответ: {correct}")

    save_users(users)
    await ask(m)
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
