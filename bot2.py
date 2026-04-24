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
ADMIN_ID = 123456789  # <-- ВСТАВЬ СВОЙ ID

DATA_FILE = "users.json"

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
            "last_q": None
        }
    return users[uid]

# ===== UI =====

def t(u, ru, kz):
    return kz if u.get("lang") == "kz" else ru

def kb_main(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(t(u,"📚 Предметы","📚 Пәндер"),
           t(u,"🧠 Тренировка","🧠 Жаттығу"))
    kb.add(t(u,"📊 Статистика","📊 Статистика"),
           t(u,"💳 Доступ","💳 Қолжетімділік"))
    kb.add(t(u,"🌐 Язык","🌐 Тіл"))
    return kb

def kb_subjects():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика","История","География","Биология")
    kb.add("⬅️ Назад")
    return kb

def kb_topics(subject):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    data = {
        "Математика": ["Алгебра","Геометрия"],
        "История": ["Казахстан","Мировая"],
        "География": ["Климат","Страны"],
        "Биология": ["Клетка","Генетика"]
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
    return text

def parse(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    q = lines[0]
    opts = [l for l in lines if l.startswith(("A)","B)","C)","D)"))]
    correct = None

    for l in lines:
        if "Ответ" in l or "Жауап" in l:
            correct = l[-1]

    return {"q": q, "opts": opts, "correct": correct}

# ===== AI =====

def build_prompt(u):
    if u["lang"] == "kz":
        return f"""
Сұрақ жаса:

Пән: {u['subject']}
Тақырып: {u['topic']}

A) ...
B) ...
C) ...
D) ...
Жауап: A
"""
    else:
        return f"""
Создай вопрос:

Предмет: {u['subject']}
Тема: {u['topic']}

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

# ===== FLOW =====

@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    u = get_user(m.from_user.id)
    await m.answer("👋 Добро пожаловать", reply_markup=kb_main(u))

@dp.message_handler(lambda m: "Предмет" in m.text or "Пән" in m.text)
async def subjects(m):
    await m.answer("Выбери предмет", reply_markup=kb_subjects())

@dp.message_handler(lambda m: m.text in ["Математика","История","География","Биология"])
async def set_sub(m):
    u = get_user(m.from_user.id)
    u["subject"] = m.text
    save_users(users)
    await m.answer("Выбери тему", reply_markup=kb_topics(m.text))

@dp.message_handler(lambda m: m.text in ["Алгебра","Геометрия","Казахстан","Мировая","Климат","Страны","Клетка","Генетика"])
async def set_topic(m):
    u = get_user(m.from_user.id)
    u["topic"] = m.text
    save_users(users)
    await m.answer("Выбери сложность", reply_markup=kb_level())

@dp.message_handler(lambda m: "Легкий" in m.text or "Средний" in m.text or "Сложный" in m.text)
async def set_level(m):
    u = get_user(m.from_user.id)
    await ask(m)

async def ask(m):
    u = get_user(m.from_user.id)

    msg = await m.answer("⏳")
    q = await gen(u)
    await msg.delete()

    u["last_q"] = q
    save_users(users)

    text = q["q"] + "\n\n" + "\n".join(q["opts"])
    await m.answer(text, reply_markup=kb_answers())

# ===== FIXED ANSWER =====

@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def ans(m):
    u = get_user(m.from_user.id)
    q = u.get("last_q")

    if not q:
        return

    ok = m.text == q["correct"]
    lang = u.get("lang","ru")

    if ok:
        u["correct"] += 1
        await m.answer("✅ Дұрыс" if lang=="kz" else "✅ Правильно")
    else:
        u["wrong"] += 1
        await m.answer(f"❌ {'Дұрыс жауап' if lang=='kz' else 'Правильный ответ'}: {q['correct']}")

    save_users(users)

    # 🔥 ГЛАВНЫЙ ФИКС — ВСЕГДА СПРАШИВАЕМ ДАЛЬШЕ
    await ask(m)

# ===== STATS =====

@dp.message_handler(lambda m: "Статистика" in m.text)
async def stats(m):
    u = get_user(m.from_user.id)
    await m.answer(f"📊\nПравильно: {u['correct']}\nОшибок: {u['wrong']}")

# ===== RUN =====

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
