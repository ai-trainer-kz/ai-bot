import os
import json
import re
import asyncio
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
used_questions = {}

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
    return load_users().get(str(uid), {}).get("lang", "ru"),

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

def difficulty_kb(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    if get_lang(uid) == "kz":
        kb.add("🟢 Жеңіл", "🔴 Қиын")
    else:
        kb.add("🟢 Легкий", "🔴 Сложный")

    kb.add(back_btn(uid))
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
    
def answers_kb(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B")
    kb.add("C","D")
    uid = str(message.from_user.id)
    kb.add(back_btn(uid))
    return kb

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("👋 Добро пожаловать!", reply_markup=main_menu(message.from_user.id))

# ===== LANGUAGE =====
@dp.message_handler(lambda m: "Тіл" in m.text or "Язык" in m.text or "🌐" in m.text)
async def lang(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский","🇰🇿 Қазақша")
    kb.add(back_btn(uid))
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
@dp.message_handler(lambda m: m.text in ["📚 Предметы", "📚 Пәндер"])
async def subjects(message: types.Message):
    await message.answer(
        t(message.from_user.id, "Выбери предмет", "Пәнді таңда"),
        reply_markup=subjects_kb(message.from_user.id)
    )

lambda m: m.text in [
    "Математика","Физика","Биология","Химия",
    "История","История мира",
    "Қазақстан тарихы","Дүниежүзі тарихы"
]
async def subject(message: types.Message):
    user_data[str(message.from_user.id)] = {"subject": message.text}
    await message.answer("Выбери сложность", reply_markup=difficulty_kb(message.from_user.id))

@dp.message_handler(lambda m: "лег" in m.text.lower() or "қиын" in m.text.lower() or "жең" in m.text.lower())
async def difficulty(message: types.Message):
    uid = str(message.from_user.id)

    user_data.setdefault(uid, {})

    if "жең" in message.text.lower() or "лег" in message.text.lower():
        user_data[uid]["level"] = "easy"
    else:
        user_data[uid]["level"] = "hard"

    await message.answer(q.strip(), reply_markup=answers_kb(uid))
# ===== AI =====
async def generate_question(subject, lang, level):
    level_text = "легкий" if level=="easy" else "сложный"
    language = "на русском языке" if lang=="ru" else "қазақ тілінде"

    prompt = f"""
Сгенерируй {level_text} тест ЕНТ {language}

Предмет: {subject}

Формат:
Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A/B/C/D
Объяснение: ...
"""

    try:
        r = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role":"user","content":prompt}]
        )
        return r.choices[0].message.content
    except:
        return """Вопрос: 2+2=?
A) 3
B) 4
C) 5
D) 6
Ответ: B
Объяснение: 2+2=4"""

async def generate_explanation(question, lang):
    try:
        r = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{
                "role": "user",
                "content": f"{'Түсіндір' if lang=='kz' else 'Объясни'}:\n{question}"
            }]
        )
        return r.choices[0].message.content

    except:
        return "Қате" if lang == "kz" else "Ошибка генерации"
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

    uid = str(message.from_user.id)

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

    explanation = data["explanation"] or await generate_explanation(data["question"], users[uid]["lang"])
    lang = get_lang(uid)

    title = "📖 Түсіндірме:\n" if lang=="kz" else "📖 Объяснение:\n"
    
    await message.answer(title + clean_text(explanation))

    await send_question(message, data["subject"])

# ===== STATS =====
@dp.message_handler(lambda m: "стат" in m.text.lower())
async def stats(message: types.Message):
    uid = str(message.from_user.id)
    u = load_users().get(uid, {})

    c = u.get("correct",0)
    w = u.get("wrong",0)
    total = c + w
    acc = round((c/total)*100,1) if total else 0

    text = f"📊\n✅ {c}\n❌ {w}\n📚 {total}\n🎯 {acc}%\n"

    topics = u.get("topics", {})
    if topics:
        text += "\n📉 Слабые темы:\n"
        for t,cnt in topics.items():
            text += f"{t} — {cnt}\n"

    await message.answer(text)

@dp.message_handler(lambda m: "тренаж" in m.text.lower())
async def trainer(message: types.Message):
    uid = str(message.from_user.id)
    u = load_users().get(uid, {})

    mistakes = u.get("mistakes", [])

    if not mistakes:
        await message.answer("Нет ошибок")
        return

    q = mistakes[-1]

    user_data[uid] = q

    await message.answer(q["question"], reply_markup=answers_kb())
# ===== TOP =====
@dp.message_handler(lambda m: m.text == "🏆 Топ")
async def top(message: types.Message):
    users=load_users()
    r=[]
    for u in users.values():
        c=u.get("correct",0); w=u.get("wrong",0)
        if c+w>0:
            r.append((u.get("name"),c,c/(c+w)))
    r.sort(key=lambda x:x[2],reverse=True)

    text="🏆 Топ:\n"
    for i,(n,c,a) in enumerate(r[:10],1):
        text+=f"{i}. {n} — {c} ({round(a*100)}%)\n"

    await message.answer(text)

# ===== PAYMENT =====
@dp.message_handler(lambda m: m.text == "💳 Оплата")
async def pay(message: types.Message):
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Я оплатил"); kb.add("⬅️ Назад")
    await message.answer("Kaspi: 4400430352720152", reply_markup=kb)

@dp.message_handler(lambda m: "оплатил" in m.text.lower())
async def paid(message: types.Message):
    u=message.from_user

    kb=InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ 7 дней", callback_data=f"give_7_{u.id}"),
        InlineKeyboardButton("✅ 30 дней", callback_data=f"give_30_{u.id}")
    )
    kb.add(InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{u.id}"))

    await bot.send_message(
        ADMIN_ID,
        f"💰 Новая оплата!\n\n👤 {u.full_name}\n📩 @{u.username}\n🆔 {u.id}",
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
    users[str(uid)]["used"]=0  # 🔥 сброс лимита

    save_users(users)

    await bot.send_message(uid,f"✅ Доступ на {days} дней")

@dp.callback_query_handler(lambda c: c.data.startswith("deny_"))
async def deny(callback_query: types.CallbackQuery):
    uid=int(callback_query.data.split("_")[-1])
    await bot.send_message(uid,"❌ Оплата отклонена")

# ===== BACK =====
@dp.message_handler(lambda m: "Назад" in m.text or "Артқа" in m.text)
async def back(message: types.Message):
    await message.answer("Меню", reply_markup=main_menu(message.from_user.id))

# ===== RUN =====
if __name__=="__main__":
    executor.start_polling(dp, skip_updates=True)
