import os
import json
import logging
import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor

API_TOKEN = os.getenv("BOT_TOKEN")

# ⚠️ РЕКВИЗИТЫ ТЕПЕРЬ ЧЕРЕЗ ENV
KASPI = os.getenv("KASPI_CARD")  # пример: 4400....
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

DATA_FILE = "users.json"

# ===== USERS =====
def load_users():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_users(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

users = load_users()

def get_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {
            "subject": None,
            "topic": None,
            "correct": 0,
            "wrong": 0,
            "last_q": None,
            "paid": False
        }
    return users[uid]

# ===== QUESTIONS =====
QUESTIONS = {
    "Математика": {
        "Алгебра": []
    },
    "История": {
        "Мировая": [
            {
                "q": "Кто открыл Америку?",
                "opts": ["A) Колумб", "B) Наполеон", "C) Цезарь", "D) Линкольн"],
                "correct": "A"
            },
            {
                "q": "В каком году началась Вторая мировая война?",
                "opts": ["A) 1939", "B) 1945", "C) 1914", "D) 1920"],
                "correct": "A"
            }
        ]
    }
}

# ===== KEYBOARDS =====
def kb_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Пәндер")
    kb.add("🧠 Жаттығу", "📊 Статистика")
    kb.add("💳 Қолжетімділік")
    return kb

def kb_subjects():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "История")
    kb.add("⬅️ Назад")
    return kb

def kb_topics(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    subj = u.get("subject")
    for t in QUESTIONS[subj]:
        kb.add(t)
    kb.add("⬅️ Назад")
    return kb

def kb_answers():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    kb.add("⬅️ Назад")
    return kb

# ===== MATH =====
def gen_math():
    a = random.randint(1, 20)
    b = random.randint(1, 20)

    correct = a + b

    options = list(set([
        correct,
        correct + random.randint(1, 5),
        correct - random.randint(1, 3),
        correct + random.randint(6, 10)
    ]))

    while len(options) < 4:
        options.append(correct + random.randint(1, 10))

    random.shuffle(options)

    letters = ["A", "B", "C", "D"]
    opts = [f"{letters[i]}) {options[i]}" for i in range(4)]

    return {
        "q": f"{a} + {b} = ?",
        "opts": opts,
        "correct": letters[options.index(correct)]
    }

# ===== START =====
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Меню", reply_markup=kb_menu())

# ===== MENU =====
@dp.message_handler(lambda m: m.text == "📚 Пәндер")
async def subjects_menu(m: types.Message):
    await m.answer("Пәнді таңда", reply_markup=kb_subjects())

@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def stats(m: types.Message):
    u = get_user(m.from_user.id)
    await m.answer(f"📊\nДұрыс: {u['correct']}\nҚате: {u['wrong']}")

@dp.message_handler(lambda m: m.text == "🧠 Жаттығу")
async def training(m: types.Message):
    u = get_user(m.from_user.id)
    if not u.get("subject") or not u.get("topic"):
        await m.answer("Алдымен пән мен тақырып таңда")
        return
    await ask(m)

# ===== PAYMENT =====
@dp.message_handler(lambda m: m.text == "💳 Қолжетімділік")
async def pay(m: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Мен төледім")
    kb.add("⬅️ Назад")

    await m.answer(
        "💳 Kaspi:\n4400430352720152\n\nТөлеген соң 'Мен төледім' басыңыз",
        reply_markup=kb
    )

@dp.message_handler(lambda m: m.text.lower() == "мен төледім")
async def paid(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    name = message.from_user.full_name

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("7 дней", callback_data=f"pay_7_{user_id}"),
        InlineKeyboardButton("30 дней", callback_data=f"pay_30_{user_id}")
    )
    kb.add(InlineKeyboardButton("❌ Отказать", callback_data=f"pay_no_{user_id}"))

    await bot.send_message(
        ADMIN_ID,
        f"💰 Оплата\n\n{name}\n@{username}\nID: {user_id}",
        reply_markup=kb
    )

    await message.answer("Күтіңіз...")

@dp.callback_query_handler(lambda c: c.data.startswith("pay_"))
async def process_payment(call: types.CallbackQuery):
    data = call.data.split("_")
    action = data[1]
    user_id = int(data[2])

    u = get_user(user_id)

    if action == "7":
        u["paid"] = True
        await bot.send_message(user_id, "✅ 7 күн ашылды")
    elif action == "30":
        u["paid"] = True
        await bot.send_message(user_id, "✅ 30 күн ашылды")
    else:
        await bot.send_message(user_id, "❌ Бас тартылды")

    save_users(users)
    await call.answer("OK")

# ===== SUBJECT =====
@dp.message_handler(lambda m: m.text in ["Математика", "История"])
async def subject(m: types.Message):
    u = get_user(m.from_user.id)
    u["subject"] = m.text
    u["topic"] = None
    save_users(users)
    await m.answer("Выбери тему", reply_markup=kb_topics(u))

# ===== MAIN =====
@dp.message_handler()
async def main_handler(m: types.Message):
    u = get_user(m.from_user.id)

    if m.text == "⬅️ Назад":
        if u.get("topic"):
            u["topic"] = None
            await m.answer("Выбери тему", reply_markup=kb_topics(u))
        else:
            u["subject"] = None
            await m.answer("Меню", reply_markup=kb_menu())
        return

    if u.get("subject") and not u.get("topic"):
        if m.text in QUESTIONS[u["subject"]]:
            u["topic"] = m.text
            save_users(users)
            await ask(m)
            return

    if m.text in ["A","B","C","D"]:
        await answer(m)

# ===== ASK =====
async def ask(m):
    u = get_user(m.from_user.id)

    if u["subject"] == "Математика":
        q = gen_math()
    else:
        q = random.choice(QUESTIONS[u["subject"]][u["topic"]])

    u["last_q"] = q
    save_users(users)

    text = q["q"] + "\n\n" + "\n".join(q["opts"])
    await m.answer(text, reply_markup=kb_answers())

# ===== ANSWER =====
async def answer(m):
    u = get_user(m.from_user.id)
    q = u.get("last_q")

    if not q:
        return

    correct = q.get("correct")

    if not correct:
        await m.answer("Ошибка")
        return

    if m.text == correct:
        u["correct"] += 1
        await m.answer("✅")
    else:
        u["wrong"] += 1
        await m.answer(f"❌ {correct}")

    save_users(users)
    await ask(m)

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
