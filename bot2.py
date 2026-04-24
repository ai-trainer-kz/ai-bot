import os
import json
import logging
import re
import time
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

API_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 8398266271

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
            "access_until": 0
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

def kb_level(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        t(u,"🟢 Легкий","🟢 Жеңіл"),
        t(u,"🟡 Средний","🟡 Орта"),
        t(u,"🔴 Сложный","🔴 Қиын")
    )
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
    text = text.replace("\\(", "").replace("\\)", "")
    return text.strip()

def parse(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    q = ""
    opts = []

    for l in lines:
        if re.match(r"^(Вопрос|Сұрақ)", l):
            q = l
        if re.match(r"^[A-D]\)", l):
            opts.append(l)

    correct_match = re.search(r"(Ответ|Жауап)\s*:\s*([A-D])", text)
    correct_letter = correct_match.group(2) if correct_match else None

    if correct_letter not in ["A","B","C","D"]:
        correct_letter = None

    expl = re.search(r"(Объяснение|Түсіндіру)\s*:\s*(.+)", text, re.DOTALL)

    return {
        "q": q or (lines[0] if lines else ""),
        "opts": opts[:4],
        "correct": correct_letter,
        "expl": expl.group(2).strip() if expl else ""
    }

# ===== AI =====

def build_prompt(u):
    if u["lang"] == "kz":
        return f"""
Тек қазақ тілінде.

Пән: {u['subject']}
Тақырып: {u['topic']}
Деңгей: {u['level']}

Сұрақ: ...
A) ...
B) ...
C) ...
D) ...
Жауап: A
Түсіндіру: ...
"""
    else:
        return f"""
Только русский язык.

Предмет: {u['subject']}
Тема: {u['topic']}
Сложность: {u['level']}

Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A
Объяснение: ...
"""

async def gen(u):
    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": build_prompt(u)}]
    )
    return parse(r.choices[0].message.content)

# ===== START =====

@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    u = get_user(m.from_user.id)
    await m.answer(t(u,"👋 Добро пожаловать","👋 Қош келдіңіз"),
                   reply_markup=kb_main(u))

# ===== ОПЛАТА =====

@dp.message_handler(lambda m: "Доступ" in m.text or "Қолжетімділік" in m.text)
async def pay(m: types.Message):
    u = get_user(m.from_user.id)
    await m.answer(
        f"Kaspi:\n4400430352720152\n\nID: {m.from_user.id}\nИмя: {m.from_user.full_name}\n\nНажми 'Я оплатил'"
    )

@dp.message_handler(lambda m: m.text == "Я оплатил")
async def paid(m: types.Message):
    global last_user

    last_user = str(m.from_user.id)

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("7 дней","30 дней","Отказать")

    await bot.send_message(
        ADMIN_ID,
        f"{m.from_user.id}|{m.from_user.full_name}",
        reply_markup=kb
    )

    await m.answer("Ожидай подтверждения")


@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text in ["7 дней","30 дней","Отказать"])
async def admin(m: types.Message):
    global last_user

    if not last_user:
        await m.answer("Нет заявки")
        return

    if m.text == "Отказать":
        await bot.send_message(last_user,"❌ Отказано")
    else:
        await bot.send_message(last_user,f"✅ Доступ: {m.text}")

    last_user = None

# ===== ОСНОВНОЕ =====

@dp.message_handler(lambda m:"Язык" in m.text or "Тіл" in m.text)
async def lang(m):
    u=get_user(m.from_user.id)
    await m.answer(t(u,"Выбери язык","Тілді таңда"),
                   reply_markup=kb_lang())

@dp.message_handler(lambda m:m.text in ["Русский","Қазақша"])
async def set_lang(m):
    u=get_user(m.from_user.id)
    u["lang"]="kz" if m.text=="Қазақша" else "ru"
    save_users(users)
    await m.answer("OK",reply_markup=kb_main(u))

@dp.message_handler(lambda m:"Предмет" in m.text or "Пән" in m.text)
async def subjects(m):
    u=get_user(m.from_user.id)
    await m.answer(t(u,"Выбери предмет","Пәнді таңда"),
                   reply_markup=kb_subjects(u))

@dp.message_handler(lambda m: m.text in ["⬅️ Назад","⬅️ Артқа","Артқа"])
async def back(m: types.Message):
    u = get_user(m.from_user.id)

    if u.get("topic"):
        u["topic"] = None
        save_users(users)
        await m.answer(
            t(u,"Выбери тему","Тақырып таңда"),
            reply_markup=kb_topics(u["subject"])
        )
        return

    if u.get("subject"):
        u["subject"] = None
        save_users(users)
        await m.answer(
            t(u,"Выбери предмет","Пәнді таңда"),
            reply_markup=kb_subjects(u)
        )
        return

    await m.answer("Меню", reply_markup=kb_main(u))

@dp.message_handler(lambda m:m.text in ["Математика","История","География","Биология"])
async def set_sub(m):
    u=get_user(m.from_user.id)
    u["subject"]=m.text
    save_users(users)
    await m.answer(t(u,"Выбери тему","Тақырып таңда"),
                   reply_markup=kb_topics(m.text))

@dp.message_handler(lambda m:m.text in [
"Алгебра","Геометрия","Проценты","Логарифмы",
"Казахстан","Мировая","Даты","Персоны",
"Климат","Страны","Ресурсы","Карты",
"Клетка","Генетика","Анатомия","Экология"])
async def set_topic(m):
    u=get_user(m.from_user.id)
    u["topic"]=m.text
    save_users(users)
    await m.answer(t(u,"Выбери сложность","Қиындық таңда"),
                   reply_markup=kb_level(u))

@dp.message_handler(lambda m:"Легкий" in m.text or "Жеңіл" in m.text)
async def lvl1(m):
    u=get_user(m.from_user.id)
    u["level"]="easy"
    await ask(m)

@dp.message_handler(lambda m:"Средний" in m.text or "Орта" in m.text)
async def lvl2(m):
    u=get_user(m.from_user.id)
    u["level"]="medium"
    await ask(m)

@dp.message_handler(lambda m:"Сложный" in m.text or "Қиын" in m.text)
async def lvl3(m):
    u=get_user(m.from_user.id)
    u["level"]="hard"
    await ask(m)

async def ask(m):
    u=get_user(m.from_user.id)
    msg=await m.answer("⏳")
    try:
        q=await gen(u)
    except:
        await msg.edit_text("Ошибка генерации")
        return

    await msg.delete()
    u["last_q"]=q
    save_users(users)

    text=f"{clean(q['q'])}\n\n"+"\n".join(q["opts"])
    await m.answer(text,reply_markup=kb_answers())

@dp.message_handler(lambda m:m.text in ["A","B","C","D"])
async def ans(m):
    u=get_user(m.from_user.id)
    q=u.get("last_q")
    if not q:
        return

    ok = m.text == q["correct"]

    if ok:
        u["correct"]+=1
        await m.answer(t(u,"✅ Правильно","✅ Дұрыс"))
    else:
        u["wrong"]+=1
        await m.answer(t(u,f"❌ Правильный ответ: {q['correct']}",
                           f"❌ Дұрыс жауап: {q['correct']}"))

    await m.answer(clean(q["expl"]))
    save_users(users)

    await ask(m)

# ===== RUN =====

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
