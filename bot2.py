import os
import json
import re
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

ADMIN_ID = 8398266271

USERS_FILE = "users.json"
user_data = {}

# 🔥 ТАРИФЫ
FREE_LIMIT = 10

# ===== UTILS =====
def clean_text(text):
    text = re.sub(r"\\\(|\\\)", "", text)
    text = re.sub(r"\\frac\{(.*?)\}\{(.*?)\}", r"\1/\2", text)
    text = text.replace("\\", "")
    return text

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def get_lang(uid):
    return load_users().get(str(uid), {}).get("lang", "ru")

# ===== KEYBOARDS =====
def main_menu(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Предметы", "📊 Статистика")
    kb.add("🏆 Топ", "💳 Оплата")
    kb.add("🌐 Тіл / Язык")
    return kb

def difficulty_kb(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Легкий", "🔴 Сложный")
    kb.add("⬅️ Назад")
    return kb

def subjects_kb(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика", "Физика")
    kb.add("Биология", "Химия")
    kb.add("История", "Тарих")
    kb.add("⬅️ Назад")
    return kb

def answers_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B")
    kb.add("C","D")
    kb.add("⬅️ Назад")
    return kb

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("👋 Добро пожаловать!", reply_markup=main_menu(message.from_user.id))

# ===== LANGUAGE =====
@dp.message_handler(lambda m: m.text == "🌐 Тіл / Язык")
async def lang(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский","🇰🇿 Қазақша")
    kb.add("⬅️ Назад")
    await message.answer("Выбери язык / Тілді таңда", reply_markup=kb)

@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский","🇰🇿 Қазақша"])
async def set_lang(message: types.Message):
    users = load_users()
    uid = str(message.from_user.id)

    users.setdefault(uid, {})
    users[uid]["lang"] = "ru" if "Русский" in message.text else "kz"

    save_users(users)
    await message.answer("✅ OK", reply_markup=main_menu(message.from_user.id))

# ===== SUBJECT =====
@dp.message_handler(lambda m: m.text == "📚 Предметы")
async def subjects(message: types.Message):
    await message.answer("Выбери предмет", reply_markup=subjects_kb(message.from_user.id))

@dp.message_handler(lambda m: m.text in ["Математика","Физика","Биология","Химия","История","Тарих"])
async def subject(message: types.Message):
    user_data[str(message.from_user.id)] = {"subject": message.text}
    await message.answer("Выбери сложность", reply_markup=difficulty_kb(message.from_user.id))

@dp.message_handler(lambda m: m.text in ["🟢 Легкий","🔴 Сложный"])
async def difficulty(message: types.Message):
    uid = str(message.from_user.id)
    user_data.setdefault(uid, {})
    user_data[uid]["level"] = "easy" if "Легкий" in message.text else "hard"

    await send_question(message, user_data[uid].get("subject","Математика"))

# ===== AI (УЛУЧШЕННЫЙ) =====
async def generate_question(subject, lang, level):
    level_text = "простое" if level=="easy" else "сложное"
    language = "на русском языке" if lang=="ru" else "қазақ тілінде"

    prompt = f"""
Ты — эксперт ЕНТ.

Сгенерируй {level_text} тест {language}.

Предмет: {subject}

СТРОГО:
1. Вопрос
2. 4 варианта (A B C D)
3. Ответ (одна буква)
4. Объяснение

Формат:
Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A
Объяснение: ...
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.7
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print("GPT ERROR:", e)
        return None

# ===== PARSER (УЛУЧШЕННЫЙ) =====
def parse_question(text):
    if not text:
        return None

    correct = re.search(r"Ответ:\s*([A-D])", text)
    explanation = re.search(r"Объяснение:\s*(.*)", text, re.DOTALL)

    return {
        "text": text,
        "correct": correct.group(1) if correct else "A",
        "explanation": explanation.group(1).strip() if explanation else ""
    }

# ===== QUESTION =====
async def send_question(message, subject):
    uid = str(message.from_user.id)
    users = load_users()

    users.setdefault(uid,{
        "used":0,
        "expire":"",
        "correct":0,
        "wrong":0,
        "name":message.from_user.full_name,
        "lang":"ru"
    })

    # 🔥 лимит
    if not users[uid]["expire"] and users[uid]["used"] >= FREE_LIMIT:
        await message.answer("💳 Лимит закончился. Купи PRO / MAX")
        return

    users[uid]["used"] += 1
    save_users(users)

    msg = await message.answer("⏳ Генерирую...")

    level = user_data.get(uid,{}).get("level","easy")
    raw = await generate_question(subject, users[uid]["lang"], level)

    if not raw:
        await msg.edit_text("❌ Ошибка генерации")
        return

    data = parse_question(raw)

    if not data:
        await msg.edit_text("❌ Ошибка парсинга")
        return

    await msg.delete()

    q = re.sub(r"Ответ:.*","",data["text"],flags=re.DOTALL)
    q = re.sub(r"Объяснение:.*","",q,flags=re.DOTALL)

    user_data.setdefault(uid,{})
    user_data[uid].update({
        "correct":data["correct"],
        "question":q,
        "explanation":data["explanation"],
        "subject":subject
    })

    await message.answer(q.strip(), reply_markup=answers_kb())

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    uid = str(message.from_user.id)
    data = user_data.get(uid)

    if not data:
        return

    users = load_users()

    users.setdefault(uid,{
        "used":0,"expire":"","correct":0,"wrong":0,
        "name":message.from_user.full_name,"lang":"ru"
    })

    if message.text == data["correct"]:
        await message.answer("✅ Правильно")
        users[uid]["correct"]+=1
    else:
        await message.answer(f"❌ Неправильно\nПравильный ответ: {data['correct']}")
        users[uid]["wrong"]+=1

    save_users(users)

    await message.answer(f"📖 {clean_text(data['explanation'])}")

    await send_question(message, data["subject"])

# ===== PAYMENT (PRO/MAX) =====
@dp.message_handler(lambda m: m.text == "💳 Оплата")
async def pay(message: types.Message):
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💎 PRO (7 дней)")
    kb.add("🚀 MAX (30 дней)")
    kb.add("⬅️ Назад")

    await message.answer("Kaspi: 4400430352720152", reply_markup=kb)

@dp.message_handler(lambda m: "pro" in m.text.lower() or "max" in m.text.lower())
async def paid(message: types.Message):
    u=message.from_user
    plan = "pro" if "pro" in message.text.lower() else "max"

    kb=InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"give_{plan}_{u.id}"),
        InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{u.id}")
    )

    await bot.send_message(
        ADMIN_ID,
        f"💰 Оплата {plan.upper()}\n{u.full_name} ({u.id})",
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith("give_"))
async def give(callback_query: types.CallbackQuery):
    _, plan, uid = callback_query.data.split("_")

    users = load_users()
    users.setdefault(uid, {})

    days = 7 if plan=="pro" else 30
    expire = datetime.now() + timedelta(days=days)

    users[uid]["expire"] = expire.strftime("%Y-%m-%d")
    users[uid]["used"] = 0

    save_users(users)

    await bot.send_message(uid, f"✅ Доступ на {days} дней")

# ===== BACK =====
@dp.message_handler(lambda m: m.text=="⬅️ Назад")
async def back(message: types.Message):
    await message.answer("Меню", reply_markup=main_menu(message.from_user.id))

# ===== RUN =====
if __name__=="__main__":
    executor.start_polling(dp, skip_updates=True)
