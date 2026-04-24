import logging
import random
import json
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup

API_TOKEN = "8315601912:AAHoo0mcZHJV8qtlDdjze7HQvM6tXgM9U88"
ADMIN_ID = 8398266271
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
            "last_q": None
        }
    return users[uid]

# ===== QUESTIONS =====
QUESTIONS = {
    "Математика": {
        "Алгебра": [
            {
                "q": "2 + 2 = ?",
                "opts": ["A) 3", "B) 4", "C) 5", "D) 6"],
                "correct": "B",
                "expl": "2+2=4"
            }
        ]
    },
    "История": {
        "Мировая": [
            {
                "q": "Кто открыл Америку?",
                "opts": ["A) Колумб", "B) Наполеон", "C) Цезарь", "D) Линкольн"],
                "correct": "A",
                "expl": "Колумб открыл Америку в 1492 году"
            }
        ]
    }
}

# ===== KEYBOARDS =====
def kb_main():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "🧠 Тренировка")
    kb.add("📊 Статистика", "💳 Доступ")
    kb.add("🌐 Язык")
    return kb

def kb_subjects():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "История")
    kb.add("⬅️ Назад")
    return kb

def kb_topics(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for t in QUESTIONS[u["subject"]]:
        kb.add(t)
    kb.add("⬅️ Назад")
    return kb

def kb_answers():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    kb.add("⬅️ Назад")
    return kb

# ===== START =====
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Меню", reply_markup=kb_main())

# ===== МЕНЮ =====
@dp.message_handler(lambda m: "Предмет" in m.text)
async def menu_subjects(m: types.Message):
    u = get_user(m.from_user.id)
    u["subject"] = None
    u["topic"] = None
    await m.answer("Выбери предмет", reply_markup=kb_subjects())

@dp.message_handler(lambda m: "Трен" in m.text)
async def menu_train(m: types.Message):
    u = get_user(m.from_user.id)
    u["subject"] = None
    u["topic"] = None
    await m.answer("Выбери предмет", reply_markup=kb_subjects())

@dp.message_handler(lambda m: "Стат" in m.text)
async def stat(m: types.Message):
    u = get_user(m.from_user.id)
    total = u["correct"] + u["wrong"]
    p = int(u["correct"] / total * 100) if total else 0
    await m.answer(f"✅ {u['correct']}\n❌ {u['wrong']}\n🎯 {p}%")

# ===== ОПЛАТА =====
@dp.message_handler(lambda m: "Доступ" in m.text)
async def pay(m: types.Message):
    await m.answer("Kaspi:\n4400430352720152\n\nНажми 'Я оплатил'")

@dp.message_handler(lambda m: "Я оплатил" in m.text)
async def paid(m: types.Message):
    user = m.from_user
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("7 дней", "30 дней", "Отказать")

    await bot.send_message(
        ADMIN_ID,
        f"💰 Оплата\nID: {user.id}\nИмя: {user.full_name}",
        reply_markup=kb
    )

    await m.answer("Ожидай подтверждения")

# ===== АДМИН =====
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text in ["7 дней", "30 дней"])
async def admin_ok(m: types.Message):
    await m.answer("✅ Одобрено")

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text == "Отказать")
async def admin_no(m: types.Message):
    await m.answer("❌ Отклонено")

# ===== ОСНОВНАЯ ЛОГИКА =====
@dp.message_handler()
async def topic_or_answer(m: types.Message):
    u = get_user(m.from_user.id)

    # назад
    if m.text == "⬅️ Назад":
        if u.get("topic"):
            u["topic"] = None
            await m.answer("Выбери тему", reply_markup=kb_topics(u))
        else:
            u["subject"] = None
            await m.answer("Выбери предмет", reply_markup=kb_subjects())
        return

    # выбор предмета
    if m.text in ["Математика", "История"]:
        u["subject"] = m.text
        u["topic"] = None
        save_users(users)
        await m.answer("Выбери тему", reply_markup=kb_topics(u))
        return

    # выбор темы
    if u.get("subject") and not u.get("topic"):
        if m.text in QUESTIONS[u["subject"]]:
            u["topic"] = m.text
            save_users(users)
            await ask(m)
            return

    # ответ
    if m.text in ["A", "B", "C", "D"]:
        await answer(m)

# ===== ВОПРОС =====
async def ask(m):
    u = get_user(m.from_user.id)

    qs = QUESTIONS[u["subject"]][u["topic"]]
    q = random.choice(qs)

    u["last_q"] = q
    save_users(users)

    text = q["q"] + "\n\n" + "\n".join(q["opts"])
    await m.answer(text, reply_markup=kb_answers())

# ===== ОТВЕТ =====
async def answer(m):
    u = get_user(m.from_user.id)
    q = u.get("last_q")

    if not q:
        return

    correct = q["correct"]

    if m.text == correct:
        u["correct"] += 1
        await m.answer("✅ Правильно")
    else:
        u["wrong"] += 1
        await m.answer(f"❌ Правильный ответ: {correct}")

    # объяснение
    if "expl" in q:
        await m.answer(q["expl"])

    save_users(users)
    await ask(m)

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
