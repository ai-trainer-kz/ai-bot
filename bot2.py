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
            "paid": False   # 🔥 фикс
        }
    return users[uid]

# ===== UI =====

def t(u, ru, kz):
    return kz if u.get("lang") == "kz" else ru

def kb_main(u):
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 "+t(u,"Предметы","Пәндер"))
    kb.add("🧠 "+t(u,"Тренировка","Жаттығу"))
    kb.add("📊 "+t(u,"Статистика","Статистика"))
    kb.add("💳 "+t(u,"Доступ","Қолжетімділік"))
    kb.add("🌐 "+t(u,"Язык","Тіл"))
    return kb

def kb_answers():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
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
Сложность: {u['level']}

Вопрос:
A)
B)
C)
D)
Ответ: A
"""

async def gen(u):
    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": build_prompt(u)}]
    )
    return parse(r.choices[0].message.content)

# ===== CORE =====

async def ask(m):
    u = get_user(m.from_user.id)

    if not u["paid"] and (u["correct"]+u["wrong"]) >= LIMIT:
        await m.answer(f"🔒 Лимит. Оплата: {KASPI}")
        return

    msg = await m.answer("⏳")

    try:
        q = await gen(u)
    except:
        await msg.edit_text("Ошибка генерации")
        return

    await msg.delete()

    u["last_q"] = q
    save_users(users)

    text = f"{clean(q['q'])}\n\n" + "\n".join(q["opts"])
    await m.answer(text, reply_markup=kb_answers())

# ===== HANDLERS =====

@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    u = get_user(m.from_user.id)
    await m.answer("Старт", reply_markup=kb_main(u))

@dp.message_handler(lambda m: "Доступ" in m.text)
async def access(m):
    await m.answer(f"Kaspi: {KASPI}\nНажми 'Я оплатил'")

@dp.message_handler(lambda m: m.text.lower() == "я оплатил")
async def paid(message: types.Message):
    await bot.send_message(
        ADMIN_ID,
        f"Оплата от {message.from_user.id}"
    )
    await message.answer("Ожидайте")

@dp.message_handler(lambda m:m.text in ["A","B","C","D"])
async def ans(m):
    u=get_user(m.from_user.id)
    q=u.get("last_q")

    if not q:
        return

    correct = q.get("correct")

    if not correct:
        await m.answer("Ошибка вопроса")
        return

    if m.text == correct:
        u["correct"]+=1
        await m.answer("✅")
    else:
        u["wrong"]+=1
        await m.answer(f"❌ {correct}")

    save_users(users)
    await ask(m)

@dp.message_handler(lambda m: "Статистика" in m.text)
async def stats(m):
    u = get_user(m.from_user.id)
    await m.answer(f"✅ {u['correct']} | ❌ {u['wrong']}")

# ===== RUN =====

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
