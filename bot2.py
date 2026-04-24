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
            "history": [],
            "last_q": None,
            "busy": False,
            "premium_until": None
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

def kb_answers():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    kb.add("⬅️ Назад")
    return kb

def kb_admin():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("7 дней","30 дней")
    kb.add("❌ Отказать")
    return kb

# ===== HELPERS =====

def clean(text):
    if not text:
        return ""
    text = re.sub(r"\\frac\{(.+?)\}\{(.+?)\}", r"(\1/\2)", text)
    text = text.replace("\\(", "").replace("\\)", "")
    return text.strip()

# ===== AI =====

async def ask(m):
    u=get_user(m.from_user.id)

    msg=await m.answer("⏳")

    try:
        r = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role":"user","content":f"""
Предмет: {u['subject']}
Тема: {u['topic']}

Сделай тест:

Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A
Объяснение: ...
"""}]
        )

        text=r.choices[0].message.content

    except:
        await msg.edit_text("Ошибка")
        return

    await msg.delete()

    lines=text.split("\n")

    q=[l for l in lines if "Вопрос" in l or "Сұрақ" in l]
    opts=[l for l in lines if re.match(r"[A-D]\)",l)]
    correct=re.search(r"Ответ:\s*([A-D])",text)
    expl=re.search(r"Объяснение:\s*(.+)",text,re.DOTALL)

    q_text=q[0] if q else lines[0]

    u["last_q"]={
        "q":q_text,
        "opts":opts,
        "correct":correct.group(1) if correct else None,
        "expl":expl.group(1) if expl else ""
    }

    save_users(users)

    # язык вопроса
    if u["lang"]=="kz":
        q_text=q_text.replace("Вопрос","Сұрақ")

    await m.answer(clean(q_text)+"\n\n"+"\n".join(opts),
                   reply_markup=kb_answers())

# ===== ANSWER =====

@dp.message_handler(lambda m:m.text in ["A","B","C","D"])
async def ans(m):
    u=get_user(m.from_user.id)
    q=u.get("last_q")
    if not q:
        return

    ok = m.text == q["correct"]

    if ok:
        u["correct"]+=1
        if u["lang"]=="kz":
            await m.answer("✅ Дұрыс")
        else:
            await m.answer("✅ Правильно")
    else:
        u["wrong"]+=1
        if u["lang"]=="kz":
            await m.answer(f"❌ Дұрыс жауап: {q['correct']}")
        else:
            await m.answer(f"❌ Правильный ответ: {q['correct']}")

    if q.get("expl"):
        await m.answer(clean(q["expl"]))

    save_users(users)

    await ask(m)

# ===== PAYMENT =====

@dp.message_handler(lambda m:"Доступ" in m.text or "Қолжетімділік" in m.text)
async def pay(m):
    u=get_user(m.from_user.id)

    text=f"""
Kaspi: 4400430352720152

ID: {m.from_user.id}
Имя: {m.from_user.full_name}

Нажми "Я оплатил"
"""
    await m.answer(text)

@dp.message_handler(lambda m:"Я оплатил" in m.text)
async def paid(m):
    text=f"""
🔥 Заявка на оплату

ID: {m.from_user.id}
Имя: {m.from_user.full_name}
"""
    await bot.send_message(ADMIN_ID,text,reply_markup=kb_admin())
    await m.answer("Отправлено администратору")

# ===== ADMIN =====

@dp.message_handler(lambda m:m.from_user.id==ADMIN_ID and m.text=="7 дней")
async def ok7(m):
    uid = m.reply_to_message.text.split("ID: ")[1].split("\n")[0]
    u=get_user(uid)
    u["premium_until"]=(datetime.now()+timedelta(days=7)).isoformat()
    save_users(users)
    await m.answer("Выдано 7 дней")

@dp.message_handler(lambda m:m.from_user.id==ADMIN_ID and m.text=="30 дней")
async def ok30(m):
    uid = m.reply_to_message.text.split("ID: ")[1].split("\n")[0]
    u=get_user(uid)
    u["premium_until"]=(datetime.now()+timedelta(days=30)).isoformat()
    save_users(users)
    await m.answer("Выдано 30 дней")

@dp.message_handler(lambda m:m.from_user.id==ADMIN_ID and "Отказать" in m.text)
async def no(m):
    await m.answer("Отклонено")

# ===== START =====

@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    u=get_user(m.from_user.id)
    await m.answer("👋 Добро пожаловать",reply_markup=kb_main(u))

# ===== RUN =====

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
