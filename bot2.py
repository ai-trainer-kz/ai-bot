import os
import json
import logging
import re
def clean_math(text):
    text = re.sub(r'\\frac\{(\d+)\}\{(\d+)\}', r'\1/\2', text)
    text = re.sub(r'\\cdot', '*', text)
    text = re.sub(r'\\times', '*', text)
    text = re.sub(r'[\{\}]', '', text)
    text = re.sub(r'\^2', '²', text)
    return text
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
API_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

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
            "history": [],   # [{topic, ok}]
            "access": True, # заглушка под оплату
            "last_q": None
        }
    return users[uid]

# ===== KEYBOARDS =====

def kb_main():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "🧠 Тренировка")
    kb.add("📊 Статистика", "🌐 Язык")
    return kb

def kb_subjects():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "История")
    kb.add("География", "Биология")
    kb.add("⬅️ Назад")
    return kb

def kb_topics(subject):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    topics_map = {
        "Математика": ["Алгебра", "Геометрия", "Проценты", "Логарифмы"],
        "История": ["Казахстан", "Мировая", "Даты", "Персоны"],
        "География": ["Климат", "Страны", "Ресурсы", "Карты"],
        "Биология": ["Клетка", "Генетика", "Анатомия", "Экология"]
    }
    for t in topics_map.get(subject, []):
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

def lang_of(u):
    return u.get("lang", "ru")

def t(u, ru, kz):
    return kz if lang_of(u) == "kz" else ru

def difficulty_scale(level):
    return {"easy": 1, "medium": 2, "hard": 3}.get(level, 1)

def next_level(u, last_ok):
    lvl = u.get("level", "easy")
    order = ["easy", "medium", "hard"]
    i = order.index(lvl)
    if last_ok and i < 2:
        return order[i+1]
    if not last_ok and i > 0:
        return order[i-1]
    return lvl

def weakest_topic(u):
    # выбираем тему, где больше ошибок
    stats = {}
    for h in u.get("history", []):
        tpc = h.get("topic")
        stats.setdefault(tpc, {"ok":0, "bad":0})
        if h.get("ok"):
            stats[tpc]["ok"] += 1
        else:
            stats[tpc]["bad"] += 1
    if not stats:
        return u.get("topic")
    worst = sorted(stats.items(), key=lambda x: (x[1]["ok"] - x[1]["bad"]))[0][0]
    return worst or u.get("topic")

def parse_question(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    q = ""
    opts = []
    for l in lines:
        if l.lower().startswith("вопрос"):
            q = l
        if re.match(r"^[A-D]\)", l):
            opts.append(l)
    correct = re.search(r"Ответ:\s*([A-D])", text)
    expl = re.search(r"Объяснение:\s*(.+)", text, re.DOTALL)
    return {
        "q": q or lines[0],
        "opts": opts[:4],
        "correct": correct.group(1) if correct else "A",
        "expl": (expl.group(1).strip() if expl else "")
    }

def build_prompt(u):
    subject = u.get("subject") or "Математика"
    topic = u.get("topic") or "Общая тема"
    level = u.get("level", "easy")
    lang = u.get("lang", "ru")

    level_desc = {
        "easy": "базовый ЕНТ уровень",
        "medium": "средний ЕНТ уровень",
        "hard": "повышенный ЕНТ уровень"
    }[level]

    return f"""
Ты — опытный преподаватель ЕНТ.

Сформируй 1 экзаменационный вопрос.
Предмет: {subject}
Тема: {topic}
Сложность: {level_desc}

ТРЕБОВАНИЯ:
- Не задавай элементарные арифметические вопросы
- Варианты правдоподобные и близкие
- Только 1 правильный ответ
- Короткое объяснение как учитель
ПРАВИЛА:
- НЕ используй LaTeX (\frac, \sqrt и т.д.)
- Пиши как обычный текст
- Дроби пиши как 1/2
- Степени как x^2
- Ответ обязательно укажи: Ответ: A/B/C/D
- Добавь объяснение: Объяснение:

ФОРМАТ СТРОГО:

Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A
Объяснение: ...

Язык: {"казахский" if lang=="kz" else "русский"}
"""

async def generate_question(u):
    prompt = build_prompt(u)
    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    text = r.choices[0].message.content
    return parse_question(text)

# ===== HANDLERS =====

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    u = get_user(message.from_user.id)
    await message.answer(t(u, "👋 Добро пожаловать!", "👋 Қош келдіңіз!"), reply_markup=kb_main())

@dp.message_handler(lambda m: "Назад" in m.text)
async def back(message: types.Message):
    u = get_user(message.from_user.id)
    await message.answer(
    clean_math(clean_text(data["text"])),
    reply_markup=answers_kb()
)

# --- Language ---
@dp.message_handler(lambda m: "Язык" in m.text or "Тіл" in m.text)
async def choose_lang(message: types.Message):
    u = get_user(message.from_user.id)
    await message.answer(t(u, "Выбери язык", "Тілді таңда"), reply_markup=kb_lang())

@dp.message_handler(lambda m: m.text in ["Русский", "Қазақша"])
async def set_lang(message: types.Message):
    u = get_user(message.from_user.id)
    u["lang"] = "kz" if "Қазақша" in message.text else "ru"
    save_users(users)
    await message.answer("✅ OK", reply_markup=kb_main())

# --- Subjects ---
@dp.message_handler(lambda m: "Предмет" in m.text)
async def subjects(message: types.Message):
    u = get_user(message.from_user.id)
    lang = user_data[uid].get("lang", "ru")

text = {
    "ru": "Выбери предмет",
    "kz": "Пәнді таңда"
}

await message.answer(text[lang])
@dp.message_handler(lambda m: m.text in ["Математика","История","География","Биология"])
async def subject_set(message: types.Message):
    u = get_user(message.from_user.id)
    u["subject"] = message.text
    save_users(users)
    await message.answer(t(u, "Выбери тему", "Тақырыпты таңда"), reply_markup=kb_topics(message.text))

# --- Topics ---
@dp.message_handler(lambda m: m.text in ["Алгебра","Геометрия","Проценты","Логарифмы",
                                        "Казахстан","Мировая","Даты","Персоны",
                                        "Климат","Страны","Ресурсы","Карты",
                                        "Клетка","Генетика","Анатомия","Экология"])
async def topic_set(message: types.Message):
    u = get_user(message.from_user.id)
    u["topic"] = message.text
    save_users(users)
    await message.answer(t(u, "Выбери сложность", "Деңгейді таңда"), reply_markup=kb_level())

# --- Level ---
@dp.message_handler(lambda m: "Легкий" in m.text)
async def level_easy(message: types.Message):
    u = get_user(message.from_user.id)
    u["level"] = "easy"
    save_users(users)
    await ask(message)

@dp.message_handler(lambda m: "Средний" in m.text)
async def level_med(message: types.Message):
    u = get_user(message.from_user.id)
    u["level"] = "medium"
    save_users(users)
    await ask(message)

@dp.message_handler(lambda m: "Сложный" in m.text)
async def level_hard(message: types.Message):
    u = get_user(message.from_user.id)
    u["level"] = "hard"
    save_users(users)
    await ask(message)

# --- Training entry ---
@dp.message_handler(lambda m: "Тренировка" in m.text)
async def training(message: types.Message):
    u = get_user(message.from_user.id)
    if not u.get("subject"):
        await message.answer(t(u, "Сначала выбери предмет", "Алдымен пәнді таңда"), reply_markup=kb_subjects())
        return
    if not u.get("topic"):
        await message.answer(t(u, "Сначала выбери тему", "Алдымен тақырыпты таңда"), reply_markup=kb_topics(u["subject"]))
        return
    await ask(message)

# --- Ask question ---
async def ask(message: types.Message):
    u = get_user(message.from_user.id)

    # адаптация: если есть история — бьем по слабой теме
    if u.get("history"):
        u["topic"] = weakest_topic(u)

    msg = await message.answer("⏳ ...")
    try:
        q = await generate_question(u)
    except Exception as e:
        print("GEN ERR:", e)
        await msg.edit_text("❌ Ошибка генерации")
        return

    await msg.delete()

    u["last_q"] = q
    save_users(users)

    text = f"{q['q']}\n\n" + "\n".join(q["opts"])
    await message.answer(text, reply_markup=kb_answers())

# --- Answer ---
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = get_user(message.from_user.id)
    q = u.get("last_q")
    if not q:
        return

    ok = (message.text == q.get("correct"))
    if ok:
        u["correct"] += 1
        await message.answer(t(u, "✅ Правильно!", "✅ Дұрыс!"))
    else:
        u["wrong"] += 1
        await message.answer(t(u, f"❌ Неправильно. Ответ: {q.get('correct')}",
                                   f"❌ Қате. Дұрыс жауап: {q.get('correct')}"))

    await message.answer(f"📖 {clean_math(data['expl'])}")

    # история + адаптация уровня
    u["history"].append({"topic": u.get("topic"), "ok": ok})
    u["level"] = next_level(u, ok)

    save_users(users)

    await ask(message)

# --- Stats ---
@dp.message_handler(lambda m: "Статистика" in m.text)
async def stats(message: types.Message):
    u = get_user(message.from_user.id)
    total = u["correct"] + u["wrong"]
    percent = int((u["correct"]/total)*100) if total else 0
    text = f"""
📊 Статистика

✅ {u['correct']}
❌ {u['wrong']}
🎯 {percent}%
"""
    await message.answer(text)

# ===== RUN =====

if __name__ == "__main__":
    if not API_TOKEN:
        print("❌ BOT_TOKEN не задан")
    else:
        executor.start_polling(dp, skip_updates=True)
