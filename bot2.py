import os
import json
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
API_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 123456789  # <-- СЮДА СВОЙ ID

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
            "busy": False
        }
    return users[uid]

# ===== UI =====
def kb_main():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "🧠 Тренировка")
    kb.add("📊 Статистика", "🌐 Язык")
    kb.add("💳 Доступ")
    return kb

def kb_subjects():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "История")
    kb.add("География", "Биология")
    kb.add("⬅️ Назад")
    return kb

def kb_topics(subject):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    data = {
        "Математика": ["Алгебра", "Геометрия", "Проценты", "Логарифмы"],
        "История": ["Казахстан", "Мировая", "Даты", "Персоны"],
        "География": ["Климат", "Страны", "Ресурсы", "Карты"],
        "Биология": ["Клетка", "Генетика", "Анатомия", "Экология"]
    }
    for t in data.get(subject, []):
        kb.add(t)
    kb.add("⬅️ Назад")
    return kb

def kb_level():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Легкий", "🟡 Средний", "🔴 Сложный")
    kb.add("⬅️ Назад")
    return kb

def kb_answers():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    kb.add("⬅️ Назад")
    return kb

def kb_lang():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Русский", "Қазақша")
    kb.add("⬅️ Назад")
    return kb

# ===== HELPERS =====
def t(u, ru, kz):
    return kz if u.get("lang") == "kz" else ru

def clean(text):
    if not text:
        return ""
    text = re.sub(r"\\frac\{(.+?)\}\{(.+?)\}", r"(\1/\2)", text)
    text = text.replace("\\(", "").replace("\\)", "")
    return text.strip()

def parse(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    q = ""
    opts = []
    for l in lines:
        if l.lower().startswith("вопрос") or l.lower().startswith("сұрақ"):
            q = l
        if re.match(r"^[A-D]\)", l):
            opts.append(l)
    correct = re.search(r"Ответ:\s*([A-D])", text)
    expl = re.search(r"Объяснение:\s*(.+)", text, re.DOTALL)
    return {
        "q": q or lines[0],
        "opts": opts[:4],
        "correct": correct.group(1) if correct else "A",
        "expl": expl.group(1).strip() if expl else ""
    }

def weakest_topic(u):
    stats = {}
    for h in u["history"]:
        tpc = h["topic"]
        stats.setdefault(tpc, {"ok":0, "bad":0})
        if h["ok"]:
            stats[tpc]["ok"] += 1
        else:
            stats[tpc]["bad"] += 1
    if not stats:
        return u["topic"]
    return sorted(stats.items(), key=lambda x: x[1]["ok"]-x[1]["bad"])[0][0]

# ===== AI =====
def build_prompt(u):
    return f"""
Ты преподаватель ЕНТ.

Сделай 1 вопрос.
Предмет: {u['subject']}
Тема: {u['topic']}
Сложность: {u['level']}

ФОРМАТ:
Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A
Объяснение: ...

Язык: {"казахский" if u["lang"]=="kz" else "русский"}
"""

async def gen(u):
    for _ in range(3):
        try:
            r = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": build_prompt(u)}]
            )
            return parse(r.choices[0].message.content)
        except:
            pass
    raise Exception("fail")

# ===== START =====
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    u = get_user(m.from_user.id)
    await m.answer(t(u,"👋 Добро пожаловать","👋 Қош келдіңіз"),reply_markup=kb_main())

# ===== ОПЛАТА =====
@dp.message_handler(lambda m:"Доступ" in m.text)
async def pay(m):
    await m.answer("Kaspi:\n4400430352720152\n\nНажми 'Я оплатил'")

@dp.message_handler(lambda m:"Я оплатил" in m.text)
async def paid(m):
    user = m.from_user
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("7 дней","30 дней","Отказать")

    await bot.send_message(
        ADMIN_ID,
        f"💰 Оплата\nID: {user.id}\nИмя: {user.full_name}",
        reply_markup=kb
    )

    await m.answer("Ожидай подтверждения")

# ===== АДМИН =====
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text in ["7 дней","30 дней"])
async def admin_ok(m):
    await m.answer("✅ Одобрено")

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and "Отказать" in m.text)
async def admin_no(m):
    await m.answer("❌ Отклонено")

# ===== ЛОГИКА =====
@dp.message_handler(lambda m:m.text in ["A","B","C","D"])
async def ans(m):
    u=get_user(m.from_user.id)
    q=u.get("last_q")
    if not q:
        return

    ok=m.text==q["correct"]

    if ok:
        u["correct"]+=1
        await m.answer("✅ Дұрыс" if u["lang"]=="kz" else "✅ Правильно")
    else:
        u["wrong"]+=1
        await m.answer(f"❌ {q['correct']}")

    if q.get("expl"):
        await m.answer(clean(q["expl"]))

    u["history"].append({"topic":u["topic"],"ok":ok})
    save_users(users)

    await ask(m)

# ===== ВОПРОС =====
async def ask(m):
    u=get_user(m.from_user.id)

    if u["busy"]:
        return
    u["busy"]=True

    msg=await m.answer("⏳")
    try:
        q=await gen(u)
    except:
        await msg.edit_text("Ошибка")
        u["busy"]=False
        return

    await msg.delete()

    u["last_q"]=q
    save_users(users)

    prefix = "Сұрақ:" if u["lang"]=="kz" else "Вопрос:"
    text=f"{prefix} {clean(q['q'])}\n\n"+"\n".join([clean(o) for o in q["opts"]])

    await m.answer(text,reply_markup=kb_answers())

    u["busy"]=False

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
