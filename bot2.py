import asyncio
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import *
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from openai import OpenAI

# =======================
# НАСТРОЙКИ
# =======================

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 123456789  # твой id

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
client = OpenAI(api_key=OPENAI_KEY)

# =======================
# ФАЙЛЫ
# =======================

QUESTIONS_FILE = "questions.json"
USERS_FILE = "users.json"

# =======================
# ЗАГРУЗКА
# =======================

def load_json(file, default):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        with open(file, "w", encoding="utf-8") as f:
            json.dump(default, f)
        return default

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

questions_db = load_json(QUESTIONS_FILE, {
    "Математика": {
        "Легкий": [
            {"q": "2+2=?", "options": ["3","4","5","6"], "correct": "B"}
        ]
    }
})

users_db = load_json(USERS_FILE, {})

user_state = {}

# =======================
# МЕНЮ
# =======================

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Тест")],
        [KeyboardButton(text="🤖 AI помощь")],
        [KeyboardButton(text="💎 Премиум")]
    ],
    resize_keyboard=True
)

# =======================
# START
# =======================

@dp.message(Command("start"))
async def start(msg: types.Message):
    uid = str(msg.from_user.id)

    if uid not in users_db:
        users_db[uid] = {"premium": False, "score": 0}
        save_json(USERS_FILE, users_db)

    await msg.answer("🚀 Добро пожаловать!", reply_markup=menu)

# =======================
# SUBJECT
# =======================

@dp.message(lambda m: m.text == "📝 Тест")
async def subject(msg: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=s, callback_data=f"s_{s}")]
        for s in questions_db.keys()
    ])
    await msg.answer("📚 Выбери предмет:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("s_"))
async def level(cb: types.CallbackQuery):
    subj = cb.data.split("_")[1]
    user_state[cb.from_user.id] = {"subj": subj}

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=l, callback_data=f"l_{l}")]
        for l in questions_db[subj].keys()
    ])
    await cb.message.answer("📊 Уровень:", reply_markup=kb)

# =======================
# START TEST
# =======================

@dp.callback_query(lambda c: c.data.startswith("l_"))
async def start_test(cb: types.CallbackQuery):
    lvl = cb.data.split("_")[1]
    uid = cb.from_user.id
    subj = user_state[uid]["subj"]

    qs = questions_db[subj][lvl]

    user_state[uid].update({
        "lvl": lvl,
        "qs": qs,
        "i": 0,
        "score": 0
    })

    await send_q(cb.message, uid)

# =======================
# QUESTION
# =======================

def ans_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A", callback_data="A"),
         InlineKeyboardButton(text="B", callback_data="B")],
        [InlineKeyboardButton(text="C", callback_data="C"),
         InlineKeyboardButton(text="D", callback_data="D")],
        [InlineKeyboardButton(text="💡 Объяснить", callback_data="exp")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back"),
         InlineKeyboardButton(text="❌ Выйти", callback_data="exit")]
    ])

async def send_q(msg, uid):
    data = user_state[uid]
    qs = data["qs"]
    i = data["i"]

    # лимит бесплатных
    if not users_db[str(uid)]["premium"] and i >= 5:
        await msg.answer("🔒 Купи премиум", reply_markup=menu)
        return

    if i >= len(qs):
        percent = int(data["score"]/len(qs)*100)
        await msg.answer(f"🎉 Результат: {percent}%")
        users_db[str(uid)]["score"] += percent
        save_json(USERS_FILE, users_db)
        user_state.pop(uid)
        return

    q = qs[i]
    data["last"] = q

    progress = int((i / len(qs)) * 10)
    bar = "█" * progress + "░" * (10 - progress)

    text = (
        f"📘 {data['subj']} | {data['lvl']}\n"
        f"{bar}\n\n"
        f"❓ {q['q']}\n\n"
        f"A) {q['options'][0]}\n"
        f"B) {q['options'][1]}\n"
        f"C) {q['options'][2]}\n"
        f"D) {q['options'][3]}"
    )

    await msg.answer(text, reply_markup=ans_kb())

# =======================
# ANSWER
# =======================

@dp.callback_query(lambda c: c.data in ["A","B","C","D"])
async def answer(cb: types.CallbackQuery):
    uid = cb.from_user.id
    data = user_state[uid]
    q = data["qs"][data["i"]]

    if cb.data == q["correct"]:
        data["score"] += 1
        await cb.message.answer("✅ Правильно")
    else:
        await cb.message.answer(f"❌ Правильный: {q['correct']}")

    data["i"] += 1
    await send_q(cb.message, uid)

# =======================
# GPT EXPLAIN
# =======================

@dp.callback_query(lambda c: c.data == "exp")
async def explain(cb: types.CallbackQuery):
    uid = cb.from_user.id
    q = user_state[uid]["last"]

    lang = cb.from_user.language_code
    lang_text = "казахском" if lang == "kk" else "русском"

    prompt = f"Объясни на {lang_text}: {q}"

    res = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    await cb.message.answer(res.choices[0].message.content)

# =======================
# BACK / EXIT
# =======================

@dp.callback_query(lambda c: c.data == "back")
async def back(cb: types.CallbackQuery):
    uid = cb.from_user.id
    if user_state[uid]["i"] > 0:
        user_state[uid]["i"] -= 1
    await send_q(cb.message, uid)

@dp.callback_query(lambda c: c.data == "exit")
async def exit(cb: types.CallbackQuery):
    user_state.pop(cb.from_user.id, None)
    await cb.message.answer("❌ Выход", reply_markup=menu)

# =======================
# PREMIUM
# =======================

def premium_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Kaspi", url="https://kaspi.kz")],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
    ])

@dp.message(lambda m: m.text == "💎 Премиум")
async def premium(msg: types.Message):
    await msg.answer(
        "💰 Премиум\n\n2000₸\nKaspi: 8707XXXXXXX",
        reply_markup=premium_kb()
    )

@dp.callback_query(lambda c: c.data == "paid")
async def paid(cb: types.CallbackQuery):
    uid = str(cb.from_user.id)
    users_db[uid]["premium"] = True
    save_json(USERS_FILE, users_db)
    await cb.message.answer("✅ Премиум активирован")

# =======================
# ADMIN
# =======================

@dp.message(Command("admin"))
async def admin(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await msg.answer("Админ: /add /stats")

@dp.message(Command("add"))
async def add(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    await msg.answer("Формат:\nПредмет|Уровень|Вопрос|A|B|C|D|Ответ")

@dp.message(Command("stats"))
async def stats(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    total = len(users_db)
    premium = sum(1 for u in users_db.values() if u["premium"])
    await msg.answer(f"👥 {total}\n💎 {premium}")

@dp.message()
async def add_q(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    if "|" not in msg.text:
        return

    try:
        subj, lvl, q, a, b, c, d, correct = msg.text.split("|")

        questions_db.setdefault(subj, {}).setdefault(lvl, []).append({
            "q": q,
            "options": [a, b, c, d],
            "correct": correct
        })

        save_json(QUESTIONS_FILE, questions_db)

        await msg.answer("✅ Добавлено")
    except:
        await msg.answer("❌ Ошибка")

# =======================
# AI CHAT
# =======================

@dp.message(lambda m: m.text == "🤖 AI помощь")
async def ai(msg: types.Message):
    await msg.answer("Задай вопрос")

@dp.message()
async def ai_chat(msg: types.Message):
    lang = msg.from_user.language_code
    system = "казахском" if lang == "kk" else "русском"

    res = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": f"Отвечай на {system}"},
            {"role": "user", "content": msg.text}
        ]
    )

    await msg.answer(res.choices[0].message.content)

# =======================
# RUN
# =======================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
