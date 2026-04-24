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

ADMIN_ID = 8398266271
KASPI = "4400430352720152"

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
                "expl": "Христофор Колумб открыл Америку в 1492 году"
            }
        ]
    }
}

# ===== KEYBOARD =====
def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "🧠 Тренировка")
    kb.add("📊 Статистика", "💳 Доступ")
    kb.add("🌐 Язык")
    return kb

def subjects_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "История")
    kb.add("⬅️ Назад")
    return kb

def topics_kb(subj):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for t in QUESTIONS[subj]:
        kb.add(t)
    kb.add("⬅️ Назад")
    return kb

def answers_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    return kb

# ===== START =====
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Добро пожаловать", reply_markup=main_kb())

# ===== MENU =====
@dp.message_handler(lambda m: "Предмет" in m.text)
async def subjects(m: types.Message):
    await m.answer("Выбери предмет", reply_markup=subjects_kb())

@dp.message_handler(lambda m: "Трен" in m.text)
async def train(m: types.Message):
    await m.answer("Выбери предмет", reply_markup=subjects_kb())

@dp.message_handler(lambda m: "Стат" in m.text)
async def stat(m: types.Message):
    u = get_user(m.from_user.id)
    total = u["correct"] + u["wrong"]
    p = int(u["correct"]/total*100) if total else 0
    await m.answer(f"✅ {u['correct']}\n❌ {u['wrong']}\n🎯 {p}%")

# ===== PAYMENT =====
@dp.message_handler(lambda m: "Доступ" in m.text)
async def pay(m: types.Message):
    await m.answer("Kaspi:\n4400430352720152\n\nНажми 'Я оплатил'")

@dp.message_handler(lambda m: "Я оплатил" in m.text)
async def paid(m: types.Message):
    u = m.from_user
    await bot.send_message(
        ADMIN_ID,
        f"💰 Оплата\nID: {u.id}\nИмя: {u.full_name}",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("7 дней","30 дней","Отказать")
    )
    await m.answer("Ожидай подтверждения")

# ===== ADMIN =====
@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text in ["7 дней","30 дней"])
async def admin_ok(m: types.Message):
    await m.answer("✅ Одобрено")

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text == "Отказать")
async def admin_no(m: types.Message):
    await m.answer("❌ Отклонено")

# ===== SUBJECT =====
@dp.message_handler(lambda m: m.text in ["Математика","История"])
async def subject(m: types.Message):
    u = get_user(m.from_user.id)
    u["subject"] = m.text
    save_users(users)
    await m.answer("Выбери тему", reply_markup=topics_kb(m.text))

# ===== TOPIC =====
@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def back(m: types.Message):
    await m.answer("Меню", reply_markup=main_kb())

@dp.message_handler()
async def topic_handler(m: types.Message):
    u = get_user(m.from_user.id)

    if u.get("subject") and not u.get("topic"):
        if m.text in QUESTIONS[u["subject"]]:
            u["topic"] = m.text
            save_users(users)
            await ask(m)

# ===== ASK =====
async def ask(m):
    u = get_user(m.from_user.id)
    q = random.choice(QUESTIONS[u["subject"]][u["topic"]])
    u["last_q"] = q
    save_users(users)

    text = f"Вопрос: {q['q']}\n\n" + "\n".join(q["opts"])
    await m.answer(text, reply_markup=answers_kb())

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
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

    if "expl" in q:
        await m.answer(q["expl"])

    save_users(users)
    await ask(m)

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
