import os
import json
import re
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

ADMIN_ID = 8398266271
USERS_FILE = "users.json"

user_data = {}

# ===== UTILS =====
def clean_text(text):
    text = re.sub(r"\\\(|\\\)", "", text)
    text = re.sub(r"\\frac\{(.*?)\}\{(.*?)\}", r"\1/\2", text)
    return text.replace("\\", "")

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

def t(uid, ru, kz):
    return kz if get_lang(uid) == "kz" else ru

def back_btn(uid):
    return "⬅️ Артқа" if get_lang(uid) == "kz" else "⬅️ Назад"

# ===== KEYBOARDS =====
def main_menu(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    if get_lang(uid) == "kz":
        kb.add("📚 Пәндер", "📊 Статистика")
        kb.add("🏆 Рейтинг", "💳 Төлем")
        kb.add("🌐 Тіл")
    else:
        kb.add("📚 Предметы", "📊 Статистика")
        kb.add("🏆 Топ", "💳 Оплата")
        kb.add("🌐 Тіл / Язык")

    return kb

def subjects_kb(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    if get_lang(uid) == "kz":
        kb.add("Математика", "Физика")
        kb.add("Биология", "Химия")
        kb.add("Қазақстан тарихы", "Дүниежүзі тарихы")
    else:
        kb.add("Математика", "Физика")
        kb.add("Биология", "Химия")
        kb.add("История", "История мира")

    kb.add(back_btn(uid))
    return kb

def difficulty_kb(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    if get_lang(uid) == "kz":
        kb.add("🟢 Жеңіл", "🔴 Қиын")
    else:
        kb.add("🟢 Легкий", "🔴 Сложный")

    kb.add(back_btn(uid))
    return kb

def answers_kb(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B")
    kb.add("C","D")
    kb.add(back_btn(uid))
    return kb

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("👋 Добро пожаловать!", reply_markup=main_menu(message.from_user.id))

# ===== LANGUAGE =====
@dp.message_handler(lambda m: "Язык" in m.text or "Тіл" in m.text)
async def lang(message: types.Message):
    uid = message.from_user.id
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский","🇰🇿 Қазақша")
    kb.add(back_btn(uid))
    await message.answer("Выбери язык / Тілді таңда", reply_markup=kb)

@dp.message_handler(lambda m: "Русский" in m.text or "Қазақша" in m.text)
async def set_lang(message: types.Message):
    users = load_users()
    uid = str(message.from_user.id)

    users.setdefault(uid, {})
    users[uid]["lang"] = "ru" if "Русский" in message.text else "kz"
    save_users(users)

    await message.answer("✅ OK", reply_markup=main_menu(message.from_user.id))

# ===== SUBJECT =====
@dp.message_handler(lambda m: "Предмет" in m.text or "Пән" in m.text)
async def subjects(message: types.Message):
    await message.answer(
        t(message.from_user.id, "Выбери предмет", "Пәнді таңда"),
        reply_markup=subjects_kb(message.from_user.id)
    )

@dp.message_handler(lambda m: m.text in [
    "Математика","Физика","Биология","Химия",
    "История","История мира",
    "Қазақстан тарихы","Дүниежүзі тарихы"
])
async def subject(message: types.Message):
    uid = str(message.from_user.id)
    user_data[uid] = {"subject": message.text}
    await message.answer(
        t(uid, "Выбери сложность", "Деңгейді таңда"),
        reply_markup=difficulty_kb(uid)
    )

# ===== DIFFICULTY =====
@dp.message_handler(lambda m: "лег" in m.text.lower() or "жең" in m.text.lower() or "қиын" in m.text.lower())
async def difficulty(message: types.Message):
    uid = str(message.from_user.id)

    user_data.setdefault(uid, {})

    if "жең" in message.text.lower() or "лег" in message.text.lower():
        user_data[uid]["level"] = "easy"
    else:
        user_data[uid]["level"] = "hard"

    await send_question(message, user_data[uid]["subject"])

# ===== AI =====
async def generate_question(subject, lang, level):
    try:
        prompt = f"""
Сделай 1 тестовый вопрос по предмету {subject}.
Сложность: {level}

СТРОГО соблюдай формат:

Вопрос: текст вопроса
A) вариант
B) вариант
C) вариант
D) вариант
Ответ: A
Объяснение: текст

Никаких лишних слов.

Язык: {"казахский" if lang == "kz" else "русский"}
"""
        r = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        return r.choices[0].message.content

    except Exception as e:
        print("ERROR:", e)
        return None
        
def parse_question(text):
    correct = re.search(r"Ответ:\s*([A-D])", text)
    explanation = re.search(r"Объяснение:\s*(.*)", text)

    return {
        "text": clean_text(text),
        "correct": correct.group(1) if correct else "A",
        "explanation": clean_text(explanation.group(1)) if explanation else ""
    }

# ===== QUESTION =====
async def send_question(message, subject):
    uid = str(message.from_user.id)
    lang = get_lang(uid)

    # ⏳ загрузка
    msg = await message.answer("⏳ Генерирую...")

    level = user_data.get(uid, {}).get("level", "easy")

    q_text = await generate_question(subject, lang, level)
    print("GPT RESPONSE:\n", q_text)
    
    try:
        data = parse_question(q_text)
    except Exception as e:
        print("PARSE ERROR:", e)
        await msg.edit_text("❌ Ошибка парсинга")
        return
    
    user_data[uid] = data
    user_data[uid]["subject"] = subject
    
    await msg.delete()
    
    await message.answer(
        clean_text(data["text"]),
        reply_markup=answers_kb()
    )
# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    uid = str(message.from_user.id)
    data = user_data.get(uid)

    if not data:
        return

    users = load_users()
    users.setdefault(uid, {"correct":0,"wrong":0})

    if message.text == data["correct"]:
        await message.answer(t(uid, "✅ Правильно", "✅ Дұрыс"))
        users[uid]["correct"] += 1
    else:
        await message.answer(
            t(uid,
              f"❌ Неправильно\nПравильный ответ: {data['correct']}",
              f"❌ Қате\nДұрыс жауап: {data['correct']}")
        )
        users[uid]["wrong"] += 1

    save_users(users)

    explanation = data["explanation"] or await generate_explanation(data["question"], users[uid]["lang"])
    title = t(uid, "📖 Объяснение:\n", "📖 Түсіндірме:\n")

    await message.answer(title + clean_text(explanation))

    await send_question(message, data["subject"])

# ===== BACK =====
@dp.message_handler(lambda m: "Назад" in m.text or "Артқа" in m.text)
async def back(message: types.Message):
    await message.answer("Меню", reply_markup=main_menu(message.from_user.id))

# ===== FALLBACK =====
@dp.message_handler()
async def fallback(message: types.Message):
    return

# ===== RUN =====
if __name__=="__main__":
    executor.start_polling(dp, skip_updates=True)
