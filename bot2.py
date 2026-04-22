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
user_results = {}

# ===== SESSION =====
def get_user_session(uid):
    uid = str(uid)
    user_results.setdefault(uid, {
        "correct": 0,
        "wrong": 0,
        "mistakes": [],
        "topics": {},
        "total": 0
    })
    return user_results[uid]

# ===== UTILS =====
def clean_text(text):
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"Вопрос\s*\d+:", "Вопрос:", text)
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

def t(uid, ru, kz):
    return kz if get_lang(uid) == "kz" else ru

# ===== KEYBOARDS =====
def main_menu(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(t(uid,"📚 Предметы","📚 Пәндер"), t(uid,"📊 Статистика","📊 Статистика"))
    kb.add(t(uid,"🏆 Топ","🏆 ТОП"), t(uid,"💳 Оплата","💳 Төлем"))
    kb.add("🧠 Тренажёр", "📖 Обучение")
    kb.add("🌐 Тіл / Язык")
    return kb

def subjects_kb(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика","Физика")
    kb.add("Биология","Химия")
    kb.add("История","Тарих")
    kb.add("⬅️ Назад")
    return kb

def difficulty_kb(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Легкий","🔴 Сложный")
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
@dp.message_handler(lambda m: m.text in ["📚 Предметы","📚 Пәндер"])
async def subjects(message: types.Message):
    await message.answer(
        t(message.from_user.id,"Выбери предмет","Пәнді таңда"),
        reply_markup=subjects_kb(message.from_user.id)
    )

@dp.message_handler(lambda m: m.text in ["Математика","Физика","Биология","Химия","История","Тарих"])
async def subject(message: types.Message):
    user_data[str(message.from_user.id)] = {"subject": message.text}
    await message.answer(t(message.from_user.id,"Выбери сложность","Қиындық таңда"), reply_markup=difficulty_kb(message.from_user.id))

@dp.message_handler(lambda m: m.text in ["🟢 Легкий","🔴 Сложный"])
async def difficulty(message: types.Message):
    uid = str(message.from_user.id)
    user_data.setdefault(uid,{})
    user_data[uid]["level"] = "easy" if "Легкий" in message.text else "hard"
    await send_question(message, user_data[uid].get("subject","Математика"))

# ===== AI =====
async def generate_question(subject, lang, level):
    prompt = f"Сгенерируй тест ЕНТ по {subject}"
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def parse_question(text):
    correct = re.search(r"Ответ:\s*([A-D])", text)
    return {
        "text": clean_text(text),
        "correct": correct.group(1) if correct else "A",
        "explanation": ""
    }
        
# ===== QUESTION =====
async def send_question(message, subject):
    uid = str(message.from_user.id)
    users = load_users()

    users.setdefault(uid,{
        "used":0,"expire":"","correct":0,"wrong":0,
        "name":message.from_user.full_name,"lang":"ru"
    })

    if not users[uid]["expire"] and users[uid]["used"]>=10:
        await message.answer("💳 Лимит закончился")
        return

    users[uid]["used"]+=1
    save_users(users)

    msg = await message.answer("⏳ Генерирую...")

    level = user_data.get(uid,{}).get("level","easy")
    raw = await generate_question(subject, users[uid]["lang"], level)
    data = parse_question(raw)

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

# ===== ANSWER + АНАЛИТИКА =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    uid = str(message.from_user.id)
    data = user_data.get(uid)

    if not data:
        return

    users = load_users()
    session = get_user_session(uid)

    users.setdefault(uid, {
        "used": 0,
        "expire": "",
        "correct": 0,
        "wrong": 0,
        "name": message.from_user.full_name,
        "lang": "ru"
    })

    subject = data.get("subject", "Общее")
    
    if message.text == data["correct"]:
        await message.answer(t(uid, "✅ Правильно", "✅ Дұрыс"))
        users[uid]["correct"] += 1
        session["correct"] += 1
    
    else:
        await message.answer(
            t(uid,
              f"❌ Неправильно\nПравильный ответ: {data['correct']}",
              f"❌ Қате\nДұрыс жауап: {data['correct']}")
        )
        users[uid]["wrong"] += 1
        session["wrong"] += 1
        session["mistakes"].append(data["question"])
        session["topics"][subject] = session["topics"].get(subject, 0) + 1
    
    session["total"] += 1
    save_users(users)

    explanation = data.get("explanation") or "Нет объяснения"
    await message.answer(f"📖 {clean_text(explanation)}")

    if session["total"] % 5 == 0:
        percent = round((session["correct"]/session["total"])*100,1)
        text=f"📊 Результат\n🎯 {percent}%\n"

        if session["topics"]:
            text+="\n📉 Слабые темы:\n"
            for t,c in session["topics"].items():
                text+=f"{t} — {c}\n"

        await message.answer(text)

    await send_question(message, subject)

# ===== ТРЕНАЖЁР =====
@dp.message_handler(lambda m: m.text == "🔁 Тренажёр")
async def trainer(message: types.Message):
    uid = str(message.from_user.id)
    session = get_user_session(uid)

    if not session["mistakes"]:
        await message.answer("Нет ошибок")
        return

    mistake = session["mistakes"][-1]

    user_data[uid] = {
        "question": mistake["question"],
        "correct": mistake["correct"],
        "subject": "Тренажёр"
    }

    await message.answer(mistake["question"], reply_markup=answers_kb())

# ===== ОБУЧЕНИЕ =====
@dp.message_handler(lambda m: m.text == "📖 Обучение")
async def learning(message: types.Message):
    uid = str(message.from_user.id)
    session = get_user_session(uid)

    if not session["topics"]:
        await message.answer("Нет слабых тем")
        return

    topic = max(session["topics"], key=session["topics"].get)

    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role":"user","content":f"Объясни тему {topic} для ЕНТ"}]
    )

    await message.answer(f"📖 {topic}\n\n{r.choices[0].message.content}")

# ===== ОПЛАТА =====
@dp.message_handler(lambda m: m.text in ["💳 Оплата","💳 Төлем"])
async def pay(message: types.Message):
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Я оплатил"); kb.add("⬅️ Назад")
    await message.answer("Kaspi: 4400430352720152", reply_markup=kb)

@dp.message_handler(lambda m: "оплатил" in m.text.lower())
async def paid(message: types.Message):
    u = message.from_user

    kb = InlineKeyboardMarkup()

    kb.add(
        InlineKeyboardButton("7 дней", callback_data=f"give_7_{u.id}"),
        InlineKeyboardButton("30 дней", callback_data=f"give_30_{u.id}")
    )

    kb.add(
        InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{u.id}")
    )

    await bot.send_message(
        ADMIN_ID,
        f"💰 Оплата\n{u.full_name}\n@{u.username}\n{u.id}",
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith("give_"))
async def give(callback_query: types.CallbackQuery):
    uid=int(callback_query.data.split("_")[-1])
    days=7 if "7" in callback_query.data else 30

    users=load_users()
    users.setdefault(str(uid),{})

    expire=datetime.now()+timedelta(days=days)
    users[str(uid)]["expire"]=expire.strftime("%Y-%m-%d")
    users[str(uid)]["used"]=0

    save_users(users)

    await bot.send_message(uid,f"Доступ {days} дней")

# ===== BACK =====
@dp.message_handler(lambda m: m.text=="⬅️ Назад")
async def back(message: types.Message):
    await message.answer("Меню", reply_markup=main_menu(message.from_user.id))

# ===== RUN =====
if __name__=="__main__":
    executor.start_polling(dp, skip_updates=True)
