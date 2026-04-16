import os
import logging
import json
from datetime import datetime, timedelta
import re

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 8398266271

FREE_MESSAGES = 10
PRICE_7 = "5000 тг"
PRICE_30 = "10000 тг"
KASPI = "4400430352720152"

MODEL = "gpt-4o-mini"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

users = {}

# ===== 💾 СОХРАНЕНИЕ =====
def save_users():
    data = {}
    for uid, u in users.items():
        data[uid] = u.copy()
        if u["premium_until"]:
            data[uid]["premium_until"] = u["premium_until"].isoformat()
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_users():
    global users
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            users = data
            for uid in users:
                if users[uid]["premium_until"]:
                    users[uid]["premium_until"] = datetime.fromisoformat(users[uid]["premium_until"])
    except:
        users = {}

# ===== КНОПКИ =====
def main_kb(user_id=None):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 Начать обучение")
    kb.add("💰 Купить доступ", "📊 Статус")
    kb.add("🌐 Язык")
    if user_id == ADMIN_ID:
        kb.add("👑 Админ")
    return kb

def subject_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📐 Математика", "📜 История")
    kb.add("🧬 Биология", "🧪 Химия")
    kb.add("⬅️ Назад")
    return kb

def level_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 База", "🟡 Средний", "🔴 Сложный")
    kb.add("⬅️ Назад")
    return kb

def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    kb.add("⬅️ Назад")
    return kb

def pay_admin_kb(user_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⚡ 7 дней", callback_data=f"give7_{user_id}"),
        InlineKeyboardButton("🚀 30 дней", callback_data=f"give30_{user_id}")
    )
    return kb

def lang_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")
    kb.add("⬅️ Назад")
    return kb

def pay_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 Оплатил")
    kb.add("⬅️ Назад")
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📋 Пользователи")
    kb.add("⬅️ Назад")
    return kb

# ===== УТИЛИТЫ =====
def ensure_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "step": "idle",
            "subject": None,
            "level": "Средний",
            "lang": "ru",
            "messages_used": 0,
            "premium_until": None,
            "history": [],
            "correct": None,
            "wrong": 0,
            "paid": False,
            "created_at": datetime.now().isoformat(),
            "welcome_done": False
        }
        save_users()

def has_access(u):
    return u["premium_until"] and datetime.now() < u["premium_until"]

def can_use(u):
    return has_access(u) or u["messages_used"] < FREE_MESSAGES

# ===== GPT =====
def system_prompt(subject, level, lang):
    if lang == "kz":
        return f"Сен ҰБТ мұғалімі ({subject})."
    return f"Ты преподаватель ЕНТ ({subject})."

def ask_gpt(u, user_text=None, mode="question"):

    if mode == "question":

        if u["lang"] == "kz":
            system = f"""
    Сен ҰБТ мұғалімі.
    
    ПӘН: {u["subject"]}
    
    СТРОГО:
    - Тек қазақ тілінде жаз
    - Тек 1 сұрақ
    
    Сұрақ:
    ...
    A) ...
    B) ...
    C) ...
    D) ...
    
    Дұрыс жауап: X
    """
        else:
            system = f"""
    Ты преподаватель ЕНТ.
    
    ПРЕДМЕТ: {u["subject"]}
    
    СТРОГО:
    - Пиши только на русском
    - Только 1 вопрос
    
    Вопрос:
    ...
    A) ...
    B) ...
    C) ...
    D) ...
    
    Правильный ответ: X
    """
    
    else:
    
        if u["lang"] == "kz":
            system = """
    Шешімін түсіндір.
    
    Тек қазақ тілінде жаз.
    """
        else:
            system = """
    Объясни решение.
    
    Пиши только на русском.
    """

    messages = [{"role": "system", "content": system}]
    messages += u["history"][-5:]

    if user_text:
        messages.append({"role": "user", "content": user_text})
    else:
        messages.append({"role": "user", "content": "Начни тест"})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
    )

    answer = resp.choices[0].message.content
    # 🔥 очистка мусора
    for s in ["\\(", "\\)", "\\[", "\\]", "**", "√", "frac", "{", "}"]:
        answer = answer.replace(s, "")

    if user_text:
        u["history"].append({"role": "user", "content": user_text})
    u["history"].append({"role": "assistant", "content": answer})

    save_users()
    return answer

# ===== СТАРТ =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[message.from_user.id]

    if not u["welcome_done"]:

        if u.get("lang") == "kz":
            await message.answer(
    """🔥 AI ЕНТ Тренер
    
    ЕНТ-ға дайындалуға дайынсың ба? 🎯
    
    🤖 Бот сұрақ қояды
    📚 Қателерді түсіндіреді
    📈 Әлсіз тұстарыңды күшейтеді
    
    Бастау үшін төменнен таңда 👇"""
            )
        else:
            await message.answer(
    """🔥 AI ЕНТ Тренер
    
    Хочешь сдать ЕНТ на высокий балл? 🎯
    
    🤖 Бот сам задаёт вопросы
    📚 Объясняет ошибки как репетитор
    📈 Прокачивает слабые темы
    
    Начни обучение прямо сейчас 👇"""
            )
    
        u["welcome_done"] = True
        save_users()
    await message.answer("Главное меню", reply_markup=main_kb(message.from_user.id))

# ===== СТАТУС =====
@dp.message_handler(lambda m: "Статус" in (m.text or ""))
async def status(message: types.Message):
    u = users[message.from_user.id]

    correct = u.get("correct_count", 0)
    wrong = u.get("wrong_count", 0)
    premium = u.get("premium", False)
    expires = u.get("expires", "нет")

    if u.get("lang") == "kz":
        text = f"""📊 Сенің статистикаң

✅ Дұрыс: {correct}
❌ Қате: {wrong}

💎 Доступ: {"Бар" if premium else "Жоқ"}
📅 Аяқталады: {expires}"""
    else:
        text = f"""📊 Твоя статистика

✅ Правильно: {correct}
❌ Ошибки: {wrong}

💎 Доступ: {"Есть" if premium else "Нет"}
📅 До: {expires}"""

    await message.answer(text)

# ===== ЯЗЫК (ФИКС) =====
@dp.message_handler(lambda m: m.text == "🌐 Язык")
async def choose_language(message: types.Message):
    await message.answer("Выбери язык / Тілді таңдаңыз", reply_markup=lang_kb())


@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def set_language(message: types.Message):
    u = users[message.from_user.id]

    if message.text == "🇰🇿 Қазақша":
        u["lang"] = "kz"
        await message.answer("🇰🇿 Тіл өзгертілді", reply_markup=main_kb(message.from_user.id))
    else:
        u["lang"] = "ru"
        await message.answer("🇷🇺 Язык изменён", reply_markup=main_kb(message.from_user.id))

    save_users()

# ===== ОБУЧЕНИЕ =====
@dp.message_handler(lambda m: "Купить доступ" in (m.text or ""))
async def buy(message: types.Message):
    
        text = f"""💰 Новый платёж!
    
    👤 @{message.from_user.username or "нет username"}
    🆔 ID: {message.from_user.id}
    📛 Имя: {message.from_user.first_name}
    """

    await bot.send_message(
        ADMIN_ID,
        text,
        reply_markup=pay_admin_kb(message.from_user.id)
    )

    await message.answer(
        f"Kaspi: {KASPI}\n7 дней — {PRICE_7}\n30 дней — {PRICE_30}",
        reply_markup=pay_kb()
    )

@dp.callback_query_handler(lambda c: c.data.startswith("give7_"))
async def give_7(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split("_")[1])

    from datetime import datetime, timedelta
    expires = datetime.now() + timedelta(days=7)

    users[user_id]["premium"] = True
    users[user_id]["expires"] = expires.strftime("%Y-%m-%d")

    save_users()

    await callback.message.answer("✅ Выдано 7 дней")
    await bot.send_message(user_id, "🎉 Вам выдан доступ на 7 дней!")


@dp.callback_query_handler(lambda c: c.data.startswith("give30_"))
async def give_30(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split("_")[1])

    from datetime import datetime, timedelta
    expires = datetime.now() + timedelta(days=30)

    users[user_id]["premium"] = True
    users[user_id]["expires"] = expires.strftime("%Y-%m-%d")

    save_users()

    await callback.message.answer("✅ Выдано 30 дней")
    await bot.send_message(user_id, "🎉 Вам выдан доступ на 30 дней!")
    
@dp.message_handler(lambda m: m.text == "📚 Начать обучение")
async def choose_subject(message: types.Message):
    users[message.from_user.id]["step"] = "subject"
    await message.answer("Выбери предмет", reply_markup=subject_kb())

@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["Математика","История","Биология","Химия"]))
async def choose_level(message: types.Message):
    u = users[message.from_user.id]
    u["subject"] = message.text.replace("📐 ", "").replace("📜 ", "").replace("🧬 ", "").replace("🧪 ", "")
    u["step"] = "level"
    await message.answer("Выбери уровень", reply_markup=level_kb())

@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["База","Средний","Сложный"]))
async def start_ai(message: types.Message):
    u = users[message.from_user.id]
    u["level"] = message.text
    u["step"] = "ai"

    text = ask_gpt(u)

    # сброс старого ответа
    u["correct"] = None
    
    match = re.search(r"(Правильный ответ|Дұрыс жауап)[:\s]*([ABCD])", text)
    if match:
        u["correct"] = match.group(2)
    
    # удалить правильный ответ из текста
    text = re.sub(r"Правильный ответ.*", "", text)
    text = re.sub(r"Дұрыс жауап.*", "", text)
    
    await message.answer(text, reply_markup=answer_kb())

# ===== НАЗАД (исправлено) =====
@dp.message_handler(lambda m: "Назад" in m.text)
async def go_back(message: types.Message):
    u = users[message.from_user.id]

    if u["step"] == "ai":
        u["step"] = "level"
        await message.answer("Выбери уровень", reply_markup=level_kb())
        return

    if u["step"] == "level":
        u["step"] = "subject"
        await message.answer("Выбери предмет", reply_markup=subject_kb())
        return

    await message.answer("Главное меню", reply_markup=main_kb(message.from_user.id))

# ===== ОТВЕТЫ =====
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def answer_buttons(message: types.Message):
    u = users[message.from_user.id]

    if u["step"] != "ai":
        return

    user_answer = message.text
    correct = u.get("correct")

    if user_answer == u.get("correct"):

    u["correct_count"] = u.get("correct_count", 0) + 1

    await message.answer("✅ Правильно!")
    else:

    u["wrong_count"] = u.get("wrong_count", 0) + 1

    await message.answer(f"❌ Неправильно! Правильный ответ: {u.get('correct')}")
    
    else:
        result = f"❌ Неправильно! Правильный ответ: {correct}"

    try:
        explain = ask_gpt(u, "Объясни решение", mode="explain")
    except:
        explain = "Разберём: правильный ответ получается через стандартные действия."

    await message.answer(result + "\n\n" + explain)

    text = ask_gpt(u)
    match = re.search(r"([ABCD])", text)
    if match:
        u["correct"] = match.group(1)

    text = re.sub(r"Правильный ответ.*", "", text)

    await message.answer(text, reply_markup=answer_kb())

# ===== АДМИН (добавлено) =====
@dp.message_handler(lambda m: m.text == "📋 Пользователи")
async def users_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    text = "📊 Пользователи:\n\n"

    for uid, u in users.items():
        text += (
            f"👤 @{uid}\n"
            f"ID: {uid}\n"
            f"Имя: {u.get('created_at')}\n\n"
        )

    await message.answer(text)

# ===== ЗАПУСК =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
