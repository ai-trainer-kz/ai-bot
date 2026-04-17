import os
import logging
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ADMIN_ID = 8398266271
KASPI_NUMBER = "4400430352720152"

DAILY_LIMIT = 3  # попыток в день

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)
dp = Dispatcher(bot)
# ========= ADMIN =========
@dp.message_handler(lambda message: message.text and message.text.startswith("/add"))
async def add_user(message: types.Message):
    print("ADD COMMAND RECEIVED")  # для логов

    if message.from_user.id != ADMIN_ID:
        await message.answer(f"❌ Ты не админ. Твой ID: {message.from_user.id}")
        return

    try:
        parts = message.text.split()
        user_id = int(parts[1])

        users = load_users()

        users[str(user_id)] = {
            "access_until": (datetime.now() + timedelta(days=7)).isoformat()
        }

        save_users(users)

        await message.answer(f"✅ Доступ выдан: {user_id}")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
# ========= DB =========
if not os.path.exists("users.json"):
    with open("users.json", "w") as f:
        json.dump({}, f)

def load_users():
    with open("users.json", "r") as f:
        return json.load(f)

def save_users(data):
    with open("users.json", "w") as f:
        json.dump(data, f, indent=4)

# ========= KEYBOARDS =========
def lang_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")
    return kb

def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "📊 Статистика")
    kb.add("🏆 Топ", "💳 Оплата")
    kb.add("🏠 Главное меню")
    return kb

def subjects_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "Физика")
    kb.add("Химия", "Биология")
    kb.add("История")
    kb.add("🔙 Назад", "🏠 Главное меню")
    return kb

def mode_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📘 5 вопросов", "🧠 20 вопросов")
    kb.add("🔙 Назад", "🏠 Главное меню")
    return kb

def level_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Легкий", "Средний", "Сложный")
    kb.add("🔙 Назад", "🏠 Главное меню")
    return kb

# ========= STATE =========
user_state = {}

# ========= AI =========
async def generate_question(subject, level, lang):
    prompt = f"""
ЕНТ вопрос
Предмет: {subject}
Сложность: {level}
Язык: {lang}

JSON:
{{"question":"","options":["A","B","C","D"],"answer":"A","topic":""}}
"""
    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role":"user","content":prompt}]
    )
    try:
        return json.loads(r.choices[0].message.content)
    except:
        return None

async def explain(q, a, lang):
    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role":"user","content":f"Объясни: {q} Ответ:{a} Язык:{lang}"}]
    )
    return r.choices[0].message.content

# ========= START =========
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    users = load_users()
    uid = str(msg.from_user.id)

    if uid not in users:
        users[uid] = {
            "name": msg.from_user.full_name,
            "access_until": None,
            "correct": 0,
            "total": 0,
            "weak": {},
            "attempts": 0,
            "last_date": ""
        }
        save_users(users)

    await msg.answer("Выбери язык", reply_markup=lang_kb())

@dp.message_handler(lambda m: m.text == "🏠 Главное меню")
async def to_main(message: types.Message):
    user_state[message.from_user.id] = {}
    await message.answer("🏠 Главное меню", reply_markup=main_kb())

@dp.message_handler(lambda m: m.text == "🔙 Назад")
async def back(message: types.Message):
    state = user_state.get(message.from_user.id, {})

if state.get("step") == "subject":
        user_state[message.from_user.id] = {"step": "menu"}
        await message.answer("Меню", reply_markup=main_kb())
        return

    if state.get("step") == "level":
        user_state[message.from_user.id] = {"step": "subject"}
        await message.answer("Выбери предмет", reply_markup=subjects_kb())
        return

    if state.get("step") == "mode":
        user_state[message.from_user.id] = {"step": "subject"}
        await message.answer("Выбери предмет", reply_markup=subjects_kb())
        return

if state.get("step") == "level":
        user_state[message.from_user.id] = {"step": "mode"}
        await message.answer("Режим", reply_markup=mode_kb())
        return

# ========= LANGUAGE =========
@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский","🇰🇿 Қазақша"])
async def lang(msg: types.Message):
    lang = "русский" if "Русский" in msg.text else "казахский"
    user_state[msg.from_user.id] = {"lang": lang}
    await msg.answer("Меню", reply_markup=main_kb())

# ========= ACCESS =========
def has_access(user_id):
    users = load_users()

    if str(user_id) not in users:
        return False

    try:
        access_until = datetime.fromisoformat(users[str(user_id)]["access_until"])
        return datetime.now() < access_until
    except:
        return False
def check_limit(uid):
    users = load_users()
    user = users[str(uid)]

    today = datetime.now().date().isoformat()

    if user["last_date"] != today:
        user["attempts"] = 0
        user["last_date"] = today

    if user["attempts"] >= DAILY_LIMIT:
        return False

    user["attempts"] += 1
    save_users(users)
    return True

# ========= FLOW =========
@dp.message_handler(lambda m: m.text == "📚 Предметы")
async def subjects(msg: types.Message):
    user_state[message.from_user.id] = {"step": "subject"}
    
    await msg.answer("Выбери предмет", reply_markup=subjects_kb())

@dp.message_handler(lambda m: m.text in ["Математика","Физика","Химия","Биология","История"])
async def mode(msg: types.Message):
    if not has_access(msg.from_user.id):
        await msg.answer("Нет доступа")
        return

    if not check_limit(msg.from_user.id):
        await msg.answer("Лимит попыток на сегодня исчерпан")
        return

    user_state[msg.from_user.id]["subject"] = msg.text
    user_state[msg.from_user.id]["step"] = "mode"
    await msg.answer("Режим", reply_markup=mode_kb())

@dp.message_handler(lambda m: "вопрос" in m.text)
async def level(msg: types.Message):
    user_state[msg.from_user.id]["count"] = 5 if "5" in msg.text else 20
    await msg.answer("Сложность", reply_markup=level_kb())

@dp.message_handler(lambda m: m.text in ["Легкий","Средний","Сложный"])
async def start_test(msg: types.Message):
    user_state[msg.from_user.id]["level"] = msg.text
    user_state[msg.from_user.id]["step"] = "test"
    
    await send_q(msg) .answer("Режим", reply_markup=mode_kb())

# ========= QUESTION =========
async def send_q(msg):
    st = user_state[msg.from_user.id]

    q = await generate_question(st["subject"], st["level"], st["lang"])
    if not q:
        await msg.answer("Ошибка")
        return

    st["q"] = q

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for o in q["options"]:
        kb.add(o)

    await msg.answer(q["question"], reply_markup=kb)

# ========= ANSWER =========
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(msg: types.Message):
    if msg.from_user.id not in user_state:
        return

    st = user_state[msg.from_user.id]
    if "q" not in st:
        return

    users = load_users()
    user = users[str(msg.from_user.id)]

    q = st["q"]

    if msg.text == q["answer"]:
        st["correct"] += 1
    else:
        topic = q.get("topic","общая")
        user["weak"][topic] = user["weak"].get(topic,0)+1

    exp = await explain(q["question"], q["answer"], st["lang"])
    await msg.answer(f"Ответ: {q['answer']}\n\n{exp}")

    st["step"] += 1

    if st["step"] >= st["count"]:
        user["correct"] += st["correct"]
        user["total"] += st["count"]
        save_users(users)

        await msg.answer(f"Результат {st['correct']}/{st['count']}", reply_markup=main_kb())
        user_state.pop(msg.from_user.id)
    else:
        await send_q(msg)

# ========= STATS =========
@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def stats(msg: types.Message):
    user_state[msg.from_user.id] = {"step": "subject"}
    if not u or u["total"] == 0:
        await msg.answer("Нет данных")
        return

    percent = int(u["correct"]/u["total"]*100)
    weak = sorted(u["weak"].items(), key=lambda x:-x[1])[:3]

    txt = "\n".join([f"{k}:{v}" for k,v in weak]) if weak else "Нет"

    await msg.answer(f"{percent}%\nСлабые темы:\n{txt}")

# ========= TOP =========
@dp.message_handler(lambda m: m.text == "🏆 Топ")
async def top(msg: types.Message):
    users = load_users()

    rating = []
    for u in users.values():
        if u["total"] > 0:
            p = int(u["correct"]/u["total"]*100)
            rating.append((u["name"], p))

    rating.sort(key=lambda x:-x[1])

    text = "🏆 ТОП:\n\n"
    for i,(n,p) in enumerate(rating[:10],1):
        text += f"{i}. {n} — {p}%\n"

    await msg.answer(text)

# ========= PAYMENT =========
@dp.message_handler(lambda m: m.text == "💳 Оплата")
async def pay(msg: types.Message):
    await msg.answer(f"Kaspi: {KASPI_NUMBER}\n7 дней 5000₸\n30 дней 10000₸")

# ========= RUN =========
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
