import os
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
ADMIN_ID = 123456789

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
client = OpenAI(api_key=OPENAI_KEY)

# =======================
# БАЗА
# =======================

QUESTIONS_FILE = "questions.json"
USERS_FILE = "users.json"

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
        users_db[uid] = {"xp": 0, "level": 1, "premium": False}
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
# КНОПКИ
# =======================

def ans_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A", callback_data="A"),
         InlineKeyboardButton(text="B", callback_data="B")],
        [InlineKeyboardButton(text="C", callback_data="C"),
         InlineKeyboardButton(text="D", callback_data="D")],
        [InlineKeyboardButton(text="💡 Объяснить", callback_data="exp")],
        [InlineKeyboardButton(text="❌ Выйти", callback_data="exit")]
    ])

def next_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Дальше", callback_data="next")]
    ])

# =======================
# ВОПРОС (Duolingo стиль)
# =======================

async def send_q(msg, uid):
    data = user_state[uid]
    qs = data["qs"]
    i = data["i"]

    if not users_db[str(uid)]["premium"] and i >= 5:
        await msg.answer("🔒 Купи премиум")
        return

    if i >= len(qs):
        xp = data["score"] * 10
        users_db[str(uid)]["xp"] += xp

        # уровень
        users_db[str(uid)]["level"] = users_db[str(uid)]["xp"] // 100 + 1

        save_json(USERS_FILE, users_db)

        await msg.answer(
            f"🎉 Тест завершён!\n"
            f"XP: +{xp}\n"
            f"Уровень: {users_db[str(uid)]['level']}"
        )
        user_state.pop(uid)
        return

    q = qs[i]
    data["last"] = q

    text = (
        f"📘 {data['subj']} | {data['lvl']}\n\n"
        f"❓ {q['q']}\n\n"
        f"A) {q['options'][0]}\n"
        f"B) {q['options'][1]}\n"
        f"C) {q['options'][2]}\n"
        f"D) {q['options'][3]}"
    )

    if "msg_id" in data:
        try:
            await bot.edit_message_text(
                chat_id=msg.chat.id,
                message_id=data["msg_id"],
                text=text,
                reply_markup=ans_kb()
            )
        except:
            pass
    else:
        sent = await msg.answer(text, reply_markup=ans_kb())
        data["msg_id"] = sent.message_id

# =======================
# ОТВЕТ
# =======================

@dp.callback_query(lambda c: c.data in ["A","B","C","D"])
async def answer(cb: types.CallbackQuery):
    uid = cb.from_user.id
    data = user_state[uid]
    q = data["qs"][data["i"]]

    if cb.data == q["correct"]:
        data["score"] += 1
        result = "✅ Правильно"
    else:
        result = f"❌ Неверно\nПравильный: {q['correct']}"

    await cb.message.edit_text(
        cb.message.text + f"\n\n{result}",
        reply_markup=next_kb()
    )

# =======================
# NEXT
# =======================

@dp.callback_query(lambda c: c.data == "next")
async def next_q(cb: types.CallbackQuery):
    uid = cb.from_user.id
    user_state[uid]["i"] += 1
    await send_q(cb.message, uid)

# =======================
# GPT ОБЪЯСНЕНИЕ
# =======================

@dp.callback_query(lambda c: c.data == "exp")
async def explain(cb: types.CallbackQuery):
    uid = cb.from_user.id
    q = user_state[uid]["last"]

    lang = cb.from_user.language_code
    lang_text = "казахском" if lang == "kk" else "русском"

    res = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{
            "role": "user",
            "content": f"Объясни на {lang_text}: {q}"
        }]
    )

    await cb.message.answer(res.choices[0].message.content)

# =======================
# ВЫЙТИ
# =======================

@dp.callback_query(lambda c: c.data == "exit")
async def exit(cb: types.CallbackQuery):
    user_state.pop(cb.from_user.id, None)
    await cb.message.answer("❌ Выход", reply_markup=menu)

# =======================
# ПРЕМИУМ
# =======================

@dp.message(lambda m: m.text == "💎 Премиум")
async def premium(msg: types.Message):
    await msg.answer("💰 Премиум: 2000₸\nKaspi: 8707XXXXXXX")

# =======================
# AI ЧАТ
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
