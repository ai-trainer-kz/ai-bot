import os
import json
import logging
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

API_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

ADMIN_ID = 8398266271
 
KASPI = "4400430352720152"

DATA_FILE = "users.json"

client = OpenAI(api_key=OPENAI_KEY)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ===== STORAGE =====

def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    return json.load(open(DATA_FILE, "r", encoding="utf-8"))

def save_users(data):
    json.dump(data, open(DATA_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

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
            "free_left": 10,
            "paid_until": None
        }
    return users[uid]

# ===== ACCESS =====

def has_access(u):
    if u["paid_until"]:
        return datetime.fromisoformat(u["paid_until"]) > datetime.now()
    return u["free_left"] > 0

# ===== KEYBOARDS =====

def kb_main():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "🧠 Тренировка")
    kb.add("📊 Статистика", "🏆 Топ")
    kb.add("💳 Купить доступ", "🌐 Язык")
    return kb

def kb_buy():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("7 дней - 5000₸")
    kb.add("30 дней - 10000₸")
    kb.add("⬅️ Назад")
    return kb

def kb_answers():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    kb.add("⬅️ Назад")
    return kb

# ===== AI =====

def build_prompt(u):
    return f"""
Сделай 1 вопрос ЕНТ
Предмет: {u['subject']}
Тема: {u['topic']}

Формат:
Вопрос:
A)
B)
C)
D)
Ответ:
Объяснение:
"""

async def gen(u):
    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role":"user","content":build_prompt(u)}]
    )
    return parse(r.choices[0].message.content)

def parse(text):
    lines=[l.strip() for l in text.split("\n") if l.strip()]
    return {
        "q": lines[0],
        "opts": lines[1:5],
        "correct": re.search(r"Ответ:\s*([A-D])", text).group(1),
        "expl": text.split("Объяснение:")[-1]
    }

# ===== HANDLERS =====

@dp.message_handler(commands=["start"])
async def start(m:types.Message):
    await m.answer("👋 Добро пожаловать", reply_markup=kb_main())

@dp.message_handler(lambda m:"Купить" in m.text)
async def buy(m):
    await m.answer(f"💳 Оплата\nKaspi: {KASPI}", reply_markup=kb_buy())

@dp.message_handler(lambda m:"7 дней" in m.text or "30 дней" in m.text)
async def pay_request(m):
    await bot.send_message(
        ADMIN_ID,
        f"Заявка:\n{m.from_user.full_name}\n@{m.from_user.username}\nID:{m.from_user.id}"
    )
    await m.answer("Отправлено админу")

@dp.message_handler(lambda m:"Тренировка" in m.text)
async def train(m):
    u=get_user(m.from_user.id)

    if not has_access(u):
        await m.answer("❌ Лимит. Купи доступ", reply_markup=kb_buy())
        return

    if u["free_left"]>0:
        u["free_left"]-=1

    q=await gen(u)
    u["last_q"]=q
    save_users(users)

    await m.answer(q["q"]+"\n"+"\n".join(q["opts"]), reply_markup=kb_answers())

@dp.message_handler(lambda m:m.text in ["A","B","C","D"])
async def ans(m):
    u=get_user(m.from_user.id)
    q=u["last_q"]

    ok=m.text==q["correct"]

    if ok:
        u["correct"]+=1
        await m.answer("✅ Правильно")
    else:
        u["wrong"]+=1
        await m.answer(f"❌ {q['correct']}")

    await m.answer(q["expl"])

    u["history"].append({"topic":u["topic"],"ok":ok})
    save_users(users)

@dp.message_handler(lambda m:"Статистика" in m.text)
async def stats(m):
    u=get_user(m.from_user.id)
    await m.answer(f"""
✅ {u['correct']}
❌ {u['wrong']}
🎯 Осталось: {u['free_left']}
""")

@dp.message_handler(lambda m:"Топ" in m.text)
async def top(m):
    rating=sorted(users.items(), key=lambda x:x[1]["correct"], reverse=True)[:5]
    text="🏆 ТОП\n"
    for i,(uid,data) in enumerate(rating,1):
        text+=f"{i}. {data['correct']}\n"
    await m.answer(text)

# ===== RUN =====

if __name__=="__main__":
    executor.start_polling(dp, skip_updates=True)
