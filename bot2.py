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
ADMIN_ID = 123456789  # <-- сюда свой ID

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

def t(u, ru, kz):
    return kz if u.get("lang") == "kz" else ru

def kb_main(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(t(u,"📚 Предметы","📚 Пәндер"),
           t(u,"🧠 Тренировка","🧠 Жаттығу"))
    kb.add(t(u,"📊 Статистика","📊 Статистика"),
           t(u,"🌐 Язык","🌐 Тіл"))
    kb.add("💳 Доступ")
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
    for _ in range(5):
        try:
            r = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": build_prompt(u)}]
            )
            q = parse(r.choices[0].message.content)

            if len(q["opts"]) == 4 and q["correct"]:
                return q

        except Exception as e:
            print("GEN ERR:", e)

    raise Exception("fail")

# ===== START =====

@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    u = get_user(m.from_user.id)
    await m.answer(t(u,"👋 Добро пожаловать","👋 Қош келдіңіз"),
                   reply_markup=kb_main(u))

# ===== ОПЛАТА =====

@dp.message_handler(lambda m: "Доступ" in m.text)
async def pay(m: types.Message):
    user = m.from_user
    await m.answer(
        f"Kaspi:\n4400430352720152\n\nID: {user.id}\nИмя: {user.full_name}\n\nНажми 'Я оплатил'"
    )

@dp.message_handler(lambda m: "Я оплатил" in m.text)
async def paid(m: types.Message):
    user = m.from_user

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("7 дней","30 дней","Отказать")

    await bot.send_message(
        ADMIN_ID,
        f"💰 Оплата\nID: {user.id}\nИмя: {user.full_name}"
    )

    await bot.send_message(ADMIN_ID,"Выбери действие",reply_markup=kb)
    await m.answer("Ожидай подтверждения")

# ===== АДМИН =====

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text in ["7 дней","30 дней"])
async def admin_ok(m: types.Message):
    await m.answer("Вставь ID пользователя")

    @dp.message_handler()
    async def give_access(msg: types.Message):
        try:
            uid = int(msg.text)
            await bot.send_message(uid,"✅ Доступ открыт")
            await msg.answer("Готово")
        except:
            await msg.answer("Ошибка")

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text == "Отказать")
async def admin_no(m: types.Message):
    await m.answer("Вставь ID пользователя")

# ===== ОТВЕТ =====

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
        await m.answer(
            t(u,
              f"❌ Правильный ответ: {q['correct']}",
              f"❌ Дұрыс жауап: {q['correct']}")
        )

    await m.answer(clean(q["expl"]))
    save_users(users)

    await ask(m)

# ===== RUN =====

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
